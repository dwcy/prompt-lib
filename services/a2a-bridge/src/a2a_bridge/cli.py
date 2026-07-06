"""Typer CLI entry point: ``a2a-bridge serve <agent>`` and ``delegate``  (T028, T033).

Two subcommands wire the v1 surface together:

* ``serve gemini`` / ``serve claude`` / ``serve codex`` — boot the chosen A2A
  adapter under uvicorn after validating ``A2A_BEARER_TOKEN``. Default ports
  differ per agent (gemini: 8766, claude: 8765, codex: 8767) so the adapters
  can run side-by-side on the same host.
* ``delegate gemini <prompt>`` / ``delegate codex <prompt>`` — open an outbound
  :class:`DelegationClient` against a peer adapter and stream parsed SSE events
  to stdout, one JSON dict per line. Exit codes are deterministic per the v1
  surface contract:
  0 completed, 1 connect refused, 2 auth fail, 3 protocol error,
  4 cancelled or failed task state.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

import typer
import uvicorn
from fastapi import FastAPI

from a2a_bridge.adapters.claude.server import build_claude_app
from a2a_bridge.adapters.codex.server import build_codex_app
from a2a_bridge.adapters.gemini.server import build_gemini_app
from a2a_bridge.client.delegation import (
    DelegationAuthError,
    DelegationClient,
    DelegationConnectError,
    DelegationError,
    DelegationProtocolError,
)
from a2a_bridge.protocol.auth import validate_token_at_startup

app = typer.Typer(help="A2A bridge: serve adapters and delegate prompts.", add_completion=False)

_DEFAULT_SERVE_HOST = "127.0.0.1"
_AGENT_DEFAULT_PORTS: dict[str, int] = {"gemini": 8766, "claude": 8765, "codex": 8767}
_AGENT_APP_FACTORIES: dict[str, Callable[..., FastAPI]] = {
    "gemini": build_gemini_app,
    "claude": build_claude_app,
    "codex": build_codex_app,
}
_DELEGATE_PEERS: frozenset[str] = frozenset({"gemini", "codex"})


@app.command()
def serve(
    agent: str = typer.Argument(..., help="Adapter to serve: 'gemini', 'claude', or 'codex'."),
    host: str = typer.Option(_DEFAULT_SERVE_HOST, help="Bind host."),
    port: int | None = typer.Option(
        None, help="Bind port (defaults: gemini=8766, claude=8765, codex=8767)."
    ),
    task_timeout_seconds: float = typer.Option(
        300.0, help="Per-task CLI subprocess timeout in seconds."
    ),
) -> None:
    """Start an A2A adapter HTTP server."""
    if agent not in _AGENT_APP_FACTORIES:
        typer.echo(f"unknown agent {agent!r}; expected 'gemini', 'claude', or 'codex'.", err=True)
        raise typer.Exit(code=2)

    bearer_token = os.environ.get("A2A_BEARER_TOKEN")
    try:
        validate_token_at_startup(bearer_token)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    assert bearer_token is not None
    resolved_port = port if port is not None else _AGENT_DEFAULT_PORTS[agent]
    factory = _AGENT_APP_FACTORIES[agent]
    factory_kwargs: dict[str, object] = {
        "bearer_token": bearer_token,
        "task_timeout_seconds": task_timeout_seconds,
        "host": host,
        "port": resolved_port,
    }
    if agent == "claude":
        factory_kwargs["cwd_allowed_roots"] = _parse_cwd_allowed_roots(
            os.environ.get("A2A_CWD_ALLOWED_ROOTS")
        )
    application = factory(**factory_kwargs)
    uvicorn.run(application, host=host, port=resolved_port, log_level="info")


def _parse_cwd_allowed_roots(raw: str | None) -> list[Path]:
    if not raw:
        return []
    return [Path(p).expanduser() for p in raw.split(os.pathsep) if p]


@app.command()
def delegate(
    peer: str = typer.Argument(..., help="Peer adapter to delegate to: 'gemini' or 'codex'."),
    prompt: str = typer.Argument(..., help="Prompt forwarded to the peer adapter."),
    peer_url: str | None = typer.Option(
        None,
        "--peer-url",
        help="Base URL of the peer adapter (defaults: gemini=http://127.0.0.1:8766, "
        "codex=http://127.0.0.1:8767).",
    ),
    timeout_seconds: float = typer.Option(
        300.0, help="Read timeout for the SSE stream in seconds."
    ),
) -> None:
    """Delegate a prompt to a peer A2A adapter and stream events to stdout."""
    if peer not in _DELEGATE_PEERS:
        typer.echo(f"unknown peer {peer!r}; expected 'gemini' or 'codex'.", err=True)
        raise typer.Exit(code=2)

    resolved_peer_url = peer_url or f"http://127.0.0.1:{_AGENT_DEFAULT_PORTS[peer]}"

    bearer_token = os.environ.get("A2A_PEER_BEARER_TOKEN") or os.environ.get("A2A_BEARER_TOKEN")
    if not bearer_token:
        typer.echo("A2A_PEER_BEARER_TOKEN (or A2A_BEARER_TOKEN) must be set.", err=True)
        raise typer.Exit(code=2)

    exit_code = asyncio.run(_run_delegate(resolved_peer_url, bearer_token, prompt, timeout_seconds))
    raise typer.Exit(code=exit_code)


async def _run_delegate(
    peer_url: str, bearer_token: str, prompt: str, timeout_seconds: float
) -> int:
    client = DelegationClient(
        peer_url=peer_url,
        peer_bearer_token=bearer_token,
        timeout_seconds=timeout_seconds,
    )

    terminal_state: str | None = None

    try:
        async for event in client.delegate(prompt):
            sys.stdout.write(json.dumps(event, separators=(",", ":")) + "\n")
            sys.stdout.flush()
            if event.get("event") == "task.state":
                state = event["data"].get("state")
                if state in {"completed", "failed", "cancelled"}:
                    terminal_state = state
    except DelegationConnectError as exc:
        typer.echo(f"connect error: {exc}", err=True)
        return 1
    except DelegationAuthError as exc:
        typer.echo(f"auth error: {exc}", err=True)
        return 2
    except DelegationProtocolError as exc:
        typer.echo(f"protocol error: {exc}", err=True)
        return 3
    except DelegationError as exc:
        typer.echo(f"delegation error: {exc}", err=True)
        return 3

    if terminal_state == "completed":
        return 0
    return 4
