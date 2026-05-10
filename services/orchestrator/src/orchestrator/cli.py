"""Typer CLI entry point for the orchestrator (T021).

``orchestrator serve`` validates the environment, runs pre-flight checks
against ``gh``, the A2A peer, and the ntfy server, prints a gradient banner,
then boots the daemon. Pre-flight failures map to deterministic exit codes
so deployment scripts can react accordingly.
"""

from __future__ import annotations

import asyncio
import subprocess

import httpx
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.text import Text

from orchestrator import daemon
from orchestrator.config import Config
from orchestrator.dashboard import OrchestratorDash

app = typer.Typer(no_args_is_help=True, add_completion=False)

_BANNER = r"""
 ██████╗ ██████╗  ██████╗██╗  ██╗███████╗███████╗████████╗██████╗  █████╗ ████████╗ ██████╗ ██████╗
██╔═══██╗██╔══██╗██╔════╝██║  ██║██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗
██║   ██║██████╔╝██║     ███████║█████╗  ███████╗   ██║   ██████╔╝███████║   ██║   ██║   ██║██████╔╝
██║   ██║██╔══██╗██║     ██╔══██║██╔══╝  ╚════██║   ██║   ██╔══██╗██╔══██║   ██║   ██║   ██║██╔══██╗
╚██████╔╝██║  ██║╚██████╗██║  ██║███████╗███████║   ██║   ██║  ██║██║  ██║   ██║   ╚██████╔╝██║  ██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
""".strip("\n")

_BANNER_GRADIENT: tuple[str, ...] = (
    "bright_magenta",
    "magenta",
    "blue",
    "blue",
    "cyan",
    "bright_cyan",
)


def _render_banner(repo: str) -> Text:
    """Render the gradient banner + a one-line title for the running repo."""
    txt = Text()
    lines = _BANNER.splitlines()
    n = len(lines)
    for i, line in enumerate(lines):
        idx = (i * len(_BANNER_GRADIENT)) // max(1, n - 1) if n > 1 else 0
        idx = min(idx, len(_BANNER_GRADIENT) - 1)
        txt.append(line + "\n", style=f"bold {_BANNER_GRADIENT[idx]}")
    txt.append(f"\n  ORCHESTRATOR · {repo}\n", style="bold bright_cyan")
    return txt


@app.command()
def serve() -> None:
    """Run the orchestrator daemon."""
    console = Console()
    err_console = Console(stderr=True)

    try:
        config = Config()  # type: ignore[call-arg]
    except ValidationError as exc:
        err_console.print("[bold red]Invalid configuration:[/]")
        for error in exc.errors():
            loc = ".".join(str(part) for part in error["loc"])
            err_console.print(f"  - {loc}: {error['msg']}")
        raise typer.Exit(code=2) from exc

    _check_gh_auth(err_console)
    _check_a2a_peer(config.a2a_peer_url, err_console)
    _check_ntfy(config.orchestrator_ntfy_base, err_console)

    console.print(_render_banner(config.orchestrator_repo))
    console.print(
        f"  poll={config.orchestrator_poll_seconds}s · "
        f"db={config.orchestrator_db_path} · "
        f"peer={config.a2a_peer_url}\n",
        style="dim",
    )

    asyncio.run(daemon.serve(config))


def _check_gh_auth(err_console: Console) -> None:
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        err_console.print("[bold red]gh auth not OK[/]: gh executable not found on PATH")
        raise typer.Exit(code=3) from exc
    if result.returncode != 0:
        err_console.print("[bold red]gh auth not OK[/]")
        if result.stderr:
            err_console.print(result.stderr.strip())
        raise typer.Exit(code=3)


def _check_a2a_peer(peer_url: str, err_console: Console) -> None:
    card_url = peer_url.rstrip("/") + "/.well-known/agent-card.json"
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(card_url)
    except httpx.HTTPError as exc:
        err_console.print(f"[bold red]a2a peer unreachable[/]: {card_url}")
        err_console.print(str(exc))
        raise typer.Exit(code=4) from exc
    if response.status_code >= 400:
        err_console.print(
            f"[bold red]a2a peer unreachable[/]: {card_url} "
            f"(status {response.status_code})"
        )
        raise typer.Exit(code=4)


def _check_ntfy(ntfy_base: str, err_console: Console) -> None:
    url = ntfy_base.rstrip("/") + "/_health"
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        err_console.print(
            f"[yellow]ntfy reachable check failed; continuing anyway[/]: {exc}"
        )
        return
    if response.status_code >= 400:
        err_console.print(
            f"[yellow]ntfy reachable check failed; continuing anyway[/]: "
            f"{url} (status {response.status_code})"
        )


@app.command()
def dash() -> None:
    """Launch the live console dashboard tailing the orchestrator event log."""
    config = Config()  # type: ignore[call-arg]
    OrchestratorDash(config).run()


def main() -> None:
    app()


if __name__ == "__main__":
    main()


__all__ = ["app", "main"]
