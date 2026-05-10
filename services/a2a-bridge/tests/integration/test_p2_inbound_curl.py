"""End-to-end integration tests for User Story 2 — inbound reception (T034).

These tests prove the Claude adapter accepts JSON-RPC ``tasks/sendSubscribe``
calls from an external client (curl during dev; eventually peer agents) and
streams the documented SSE lifecycle. They are the symmetric counterpart of
``test_p1_outbound_delegation.py``: instead of a ``DelegationClient`` driving
a Gemini adapter, an ``httpx.AsyncClient`` plays the part of curl / a peer
agent and drives the Claude adapter directly over HTTP.

A real uvicorn server in a background thread (not ``ASGITransport``) is used
so the SSE stream is incrementally observable — buffering would mask every
streaming bug the user-story acceptance scenarios are meant to catch.

Coverage maps to the four User Story 2 acceptance scenarios in
``specs/001-a2a-bridge/spec.md``:

1. Happy path — Claude-shaped fake CLI streams the documented
   ``submitted -> working -> artifact -> completed`` sequence within budget.
2. Missing bearer — request returns HTTP 401 with the documented body and
   zero SSE events on the wire (auth rejects before any task lifecycle).
3. Wrong bearer — same shape as #2 but with a non-matching token.
4. CLI non-zero exit — final ``task.state`` is ``failed`` with
   ``reason="cli_nonzero_exit"``, ``exit_code=2``, and the stderr tail
   surfaces the subprocess's "boom" diagnostic.
5. Real Claude CLI — same shape as #1 but exercises the production binary;
   skips unless both ``claude`` is on PATH and the user explicitly opts in
   via ``A2A_REAL_CLI_TESTS=1`` (Claude Code may need interactive ``/login``
   before it returns useful content; we don't want silent CI failures).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import sys
import threading
import time
import uuid
from collections.abc import Callable, Iterator

import httpx
import pytest
import uvicorn

from a2a_bridge.adapters.claude.runner import claude_command_factory
from a2a_bridge.adapters.claude.server import build_claude_app

BEARER_TOKEN = "INTEGRATION_TEST_TOKEN_AT_LEAST_32_CHARS_X"
WRONG_BEARER_TOKEN = "WRONG_TOKEN_AT_LEAST_32_CHARS_XXXXXXXXX"
TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})

CliCommandFactory = Callable[[str], list[str]]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


_CLAUDE_HAPPY_PATH_SCRIPT = (
    "import json,sys;"
    "events=["
    '{"type":"system","subtype":"init"},'
    '{"type":"assistant","message":{"role":"assistant",'
    '"content":[{"type":"text","text":"pong"}]}},'
    '{"type":"result","subtype":"success"}'
    "];"
    "[print(json.dumps(e),flush=True) for e in events]"
)


def _claude_happy_path_factory() -> CliCommandFactory:
    def factory(prompt: str) -> list[str]:
        del prompt
        return [sys.executable, "-c", _CLAUDE_HAPPY_PATH_SCRIPT]

    return factory


def _fake_factory(case: str) -> CliCommandFactory:
    def factory(prompt: str) -> list[str]:
        return [
            sys.executable,
            "-m",
            "tests.fixtures.fake_cli",
            "--case",
            case,
            "--prompt",
            prompt,
        ]

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
    *, cli_command_factory: CliCommandFactory, task_timeout_seconds: float
) -> tuple[str, int, threading.Thread, uvicorn.Server]:
    host = "127.0.0.1"
    port = _free_port()
    app = build_claude_app(
        bearer_token=BEARER_TOKEN,
        cli_command_factory=cli_command_factory,
        task_timeout_seconds=task_timeout_seconds,
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
def claude_server_happy_path() -> Iterator[tuple[str, int, str]]:
    host, port, thread, server = _start_server(
        cli_command_factory=_claude_happy_path_factory(),
        task_timeout_seconds=30.0,
    )
    try:
        yield host, port, BEARER_TOKEN
    finally:
        _stop_server(thread, server)


@pytest.fixture
def claude_server_nonzero_exit() -> Iterator[tuple[str, int, str]]:
    host, port, thread, server = _start_server(
        cli_command_factory=_fake_factory("nonzero_exit"),
        task_timeout_seconds=10.0,
    )
    try:
        yield host, port, BEARER_TOKEN
    finally:
        _stop_server(thread, server)


@pytest.fixture
def claude_server_real() -> Iterator[tuple[str, int, str]]:
    host, port, thread, server = _start_server(
        cli_command_factory=claude_command_factory,
        task_timeout_seconds=60.0,
    )
    try:
        yield host, port, BEARER_TOKEN
    finally:
        _stop_server(thread, server)


def _send_subscribe_body(prompt: str) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tasks/sendSubscribe",
        "params": {"task": {"messages": [{"role": "user", "content": prompt}]}},
    }


async def _drain_sse_until_terminal(
    response: httpx.Response, *, deadline_seconds: float
) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    pending_event: str | None = None
    pending_data: list[str] = []

    async def _drain() -> None:
        nonlocal pending_event, pending_data
        async for line in response.aiter_lines():
            if line == "":
                if pending_event is not None and pending_data:
                    payload = json.loads("\n".join(pending_data))
                    events.append((pending_event, payload))
                    if pending_event == "task.state":
                        state = payload.get("state")
                        if isinstance(state, str) and state in TERMINAL_STATES:
                            return
                pending_event = None
                pending_data = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                pending_event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                pending_data.append(line[len("data:") :].lstrip())

    await asyncio.wait_for(_drain(), timeout=deadline_seconds)
    return events


def _state_payloads(
    events: list[tuple[str, dict[str, object]]],
) -> list[dict[str, object]]:
    return [payload for name, payload in events if name == "task.state"]


def _artifact_payloads(
    events: list[tuple[str, dict[str, object]]],
) -> list[dict[str, object]]:
    return [payload for name, payload in events if name == "task.artifact"]


async def test_p2_curl_happy_path_streams_artifact(
    claude_server_happy_path: tuple[str, int, str],
) -> None:
    host, port, token = claude_server_happy_path
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = _send_subscribe_body("ping")
    timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST", f"http://{host}:{port}/jsonrpc", json=body, headers=headers
        ) as response:
            assert response.status_code == 200
            events = await _drain_sse_until_terminal(response, deadline_seconds=10.0)
    elapsed = time.monotonic() - started

    states = _state_payloads(events)
    artifacts = _artifact_payloads(events)
    assert states, "expected at least one task.state event"
    assert states[0].get("state") == "submitted"
    assert any(s.get("state") == "working" for s in states)
    assert states[-1].get("state") == "completed"
    assert artifacts, "expected at least one task.artifact event"
    first_artifact = artifacts[0].get("artifact")
    assert isinstance(first_artifact, dict)
    content = first_artifact.get("content")
    assert isinstance(content, str) and content != ""
    assert "pong" in content
    assert elapsed < 10.0


async def test_p2_curl_missing_bearer_returns_401_no_events(
    claude_server_happy_path: tuple[str, int, str],
) -> None:
    host, port, _ = claude_server_happy_path
    headers = {"Content-Type": "application/json"}
    body = _send_subscribe_body("ping")
    timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"http://{host}:{port}/jsonrpc", json=body, headers=headers
        )
    elapsed = time.monotonic() - started

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}
    assert b"event:" not in response.content
    assert elapsed < 5.0


async def test_p2_curl_wrong_bearer_returns_401_no_events(
    claude_server_happy_path: tuple[str, int, str],
) -> None:
    host, port, _ = claude_server_happy_path
    headers = {
        "Authorization": f"Bearer {WRONG_BEARER_TOKEN}",
        "Content-Type": "application/json",
    }
    body = _send_subscribe_body("ping")
    timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"http://{host}:{port}/jsonrpc", json=body, headers=headers
        )
    elapsed = time.monotonic() - started

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}
    assert b"event:" not in response.content
    assert elapsed < 5.0


async def test_p2_curl_cli_nonzero_exit_emits_failed_with_stderr_tail(
    claude_server_nonzero_exit: tuple[str, int, str],
) -> None:
    host, port, token = claude_server_nonzero_exit
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = _send_subscribe_body("ping")
    timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST", f"http://{host}:{port}/jsonrpc", json=body, headers=headers
        ) as response:
            assert response.status_code == 200
            events = await _drain_sse_until_terminal(response, deadline_seconds=10.0)
    elapsed = time.monotonic() - started

    states = _state_payloads(events)
    assert states, "expected at least one task.state event"
    terminal = states[-1]
    assert terminal.get("state") == "failed"
    assert terminal.get("reason") == "cli_nonzero_exit"
    assert terminal.get("exit_code") == 2
    stderr_tail = terminal.get("stderr_tail")
    assert isinstance(stderr_tail, str)
    assert "boom" in stderr_tail
    assert elapsed < 10.0


@pytest.mark.skipif(
    shutil.which("claude") is None or not os.environ.get("A2A_REAL_CLI_TESTS"),
    reason=(
        "claude CLI not installed OR A2A_REAL_CLI_TESTS not set; the real CLI "
        "may require interactive /login before it returns useful content, so "
        "this test runs only when the operator explicitly opts in"
    ),
)
async def test_p2_curl_real_claude_completes(
    claude_server_real: tuple[str, int, str],
) -> None:
    host, port, token = claude_server_real
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = _send_subscribe_body("Reply with the single word: pong")
    timeout = httpx.Timeout(connect=5.0, read=70.0, write=5.0, pool=5.0)

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST", f"http://{host}:{port}/jsonrpc", json=body, headers=headers
        ) as response:
            assert response.status_code == 200
            events = await asyncio.wait_for(
                _drain_sse_until_terminal(response, deadline_seconds=70.0),
                timeout=70.0,
            )
    elapsed = time.monotonic() - started

    states = _state_payloads(events)
    artifacts = _artifact_payloads(events)
    assert states, "expected at least one task.state event"
    assert states[-1].get("state") == "completed", (
        f"expected completed terminal state, got {[s.get('state') for s in states]}"
    )
    assert artifacts, "expected at least one task.artifact event from real claude"
    first_artifact = artifacts[0].get("artifact")
    assert isinstance(first_artifact, dict)
    content = first_artifact.get("content")
    assert isinstance(content, str) and content != ""
    assert elapsed < 70.0
