"""End-to-end integration tests for User Story 3 — Agent Card discovery (T036).

These tests prove the discovery surface works against real uvicorn HTTP
servers running in background threads (mirroring T030/T034) for both shipped
adapters: Claude and Gemini. ASGITransport would still surface the JSON body
correctly here, but real uvicorn matches the deployed wire shape (header
casing, content negotiation) and keeps the integration tier honest.

Coverage maps to the two User Story 3 acceptance scenarios in
``specs/001-a2a-bridge/spec.md``:

1. Discovery is unauthenticated — GET ``/.well-known/agent-card.json`` with
   no ``Authorization`` header returns 200 and ``application/json``.
2. The card validates against ``contracts/agent-card.schema.json`` and the
   adapter-specific identity fields (name, skill id) are correct.

Both adapters' CLI command factories are no-op stubs (``python -c "pass"``)
because discovery never invokes the JSON-RPC dispatcher; this keeps the
tests deterministic without ``claude`` or ``gemini`` installed.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import jsonschema
import pytest
import uvicorn

from a2a_bridge.adapters.claude.server import build_claude_app
from a2a_bridge.adapters.gemini.server import build_gemini_app

BEARER_TOKEN = "INTEGRATION_TEST_TOKEN_AT_LEAST_32_CHARS_X"

CliCommandFactory = Callable[[str], list[str]]

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "specs"
    / "001-a2a-bridge"
    / "contracts"
    / "agent-card.schema.json"
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _noop_factory() -> CliCommandFactory:
    def factory(prompt: str) -> list[str]:
        del prompt
        return [sys.executable, "-c", "pass"]

    return factory


def _wait_for_server_ready(host: str, port: int, *, deadline_seconds: float = 5.0) -> None:
    url = f"http://{host}:{port}/.well-known/agent-card.json"
    deadline = time.monotonic() + deadline_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=0.2)
            if response.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(0.05)
    raise RuntimeError(
        f"uvicorn server on {host}:{port} did not become ready within "
        f"{deadline_seconds}s: {last_error!r}"
    )


def _start_server(
    *, app_builder: Callable[..., object], cli_command_factory: CliCommandFactory
) -> tuple[str, int, threading.Thread, uvicorn.Server]:
    host = "127.0.0.1"
    port = _free_port()
    app = app_builder(
        bearer_token=BEARER_TOKEN,
        cli_command_factory=cli_command_factory,
        task_timeout_seconds=30.0,
        host=host,
        port=port,
    )
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="error",
        lifespan="off",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_for_server_ready(host, port)
    return host, port, thread, server


def _stop_server(thread: threading.Thread, server: uvicorn.Server) -> None:
    server.should_exit = True
    thread.join(timeout=3.0)


@pytest.fixture
def gemini_server() -> Iterator[tuple[str, int]]:
    """Function-scoped to keep tests fully independent — the 1-2s startup cost is acceptable."""
    host, port, thread, server = _start_server(
        app_builder=build_gemini_app,
        cli_command_factory=_noop_factory(),
    )
    try:
        yield host, port
    finally:
        _stop_server(thread, server)


@pytest.fixture
def claude_server() -> Iterator[tuple[str, int]]:
    """Function-scoped to keep tests fully independent — the 1-2s startup cost is acceptable."""
    host, port, thread, server = _start_server(
        app_builder=build_claude_app,
        cli_command_factory=_noop_factory(),
    )
    try:
        yield host, port
    finally:
        _stop_server(thread, server)


def _load_schema() -> dict[str, object]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


async def test_p3_gemini_agent_card_returns_200_without_auth(
    gemini_server: tuple[str, int],
) -> None:
    host, port = gemini_server
    timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(f"http://{host}:{port}/.well-known/agent-card.json")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    assert isinstance(response.json(), dict)
    assert elapsed < 5.0


async def test_p3_claude_agent_card_returns_200_without_auth(
    claude_server: tuple[str, int],
) -> None:
    host, port = claude_server
    timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(f"http://{host}:{port}/.well-known/agent-card.json")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    assert isinstance(response.json(), dict)
    assert elapsed < 5.0


async def test_p3_gemini_agent_card_validates_against_schema(
    gemini_server: tuple[str, int],
) -> None:
    host, port = gemini_server
    schema = _load_schema()
    timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(f"http://{host}:{port}/.well-known/agent-card.json")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    card = response.json()
    jsonschema.validate(instance=card, schema=schema)
    assert card["name"] == "gemini-a2a-adapter"
    assert card["protocols"] == ["json-rpc-2.0"]
    assert card["capabilities"]["streaming"] is True
    assert card["authentication"]["schemes"] == ["bearer"]
    assert isinstance(card["skills"], list) and len(card["skills"]) >= 1
    assert card["skills"][0]["id"] == "gemini-prompt"
    assert elapsed < 5.0


async def test_p3_claude_agent_card_validates_against_schema(
    claude_server: tuple[str, int],
) -> None:
    host, port = claude_server
    schema = _load_schema()
    timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(f"http://{host}:{port}/.well-known/agent-card.json")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    card = response.json()
    jsonschema.validate(instance=card, schema=schema)
    assert card["name"] == "claude-code-a2a-adapter"
    assert card["protocols"] == ["json-rpc-2.0"]
    assert card["capabilities"]["streaming"] is True
    assert card["authentication"]["schemes"] == ["bearer"]
    assert isinstance(card["skills"], list) and len(card["skills"]) >= 1
    assert card["skills"][0]["id"] == "claude-prompt"
    assert elapsed < 5.0
