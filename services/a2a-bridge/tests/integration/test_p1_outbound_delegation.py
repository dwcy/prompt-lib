"""End-to-end integration tests for User Story 1 — outbound delegation (T030).

These tests prove the MVP wire path works against a real uvicorn HTTP server
running in a background thread, not the in-process ``httpx.ASGITransport``
shortcut used by the contract tests. That distinction matters because
``ASGITransport`` buffers the entire SSE response before yielding lines, which
hides every streaming bug — and User Story 1 is fundamentally a streaming
contract: SSE events arrive incrementally, ``tasks/cancel`` must be servable
*while* the original stream is still working, and connect / auth failures must
fail fast.

Coverage maps to the three User Story 1 acceptance scenarios in
``specs/001-a2a-bridge/spec.md`` plus the deferred mid-stream cancel behaviour
from ``TestCancelWorkingTask``:

1. Happy path — fake CLI streams ``submitted -> working -> artifact ->
   completed`` within SC-001's 30s budget (we assert <10s for the fake CLI).
2. Peer unreachable — :class:`DelegationConnectError` raised within SC-006's
   5s budget when the peer port has nothing listening.
3. Bearer token mismatch — :class:`DelegationAuthError` raised within 5s when
   the peer rejects the token.
4. Cancel while working — fake CLI in ``timeout`` mode hangs; client opens the
   stream, waits for ``working``, sends ``tasks/cancel`` over a side channel,
   and observes a final ``cancelled`` state with ``reason="client_cancelled"``.
5. Real Gemini CLI — same shape as #1 but exercises the production CLI; skips
   when ``gemini`` is not on ``PATH``.
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
from collections.abc import AsyncIterator, Callable, Iterator

import httpx
import pytest
import pytest_asyncio
import uvicorn

from a2a_bridge.adapters.gemini.runner import gemini_command_factory
from a2a_bridge.adapters.gemini.server import build_gemini_app
from a2a_bridge.client.delegation import (
    DelegationAuthError,
    DelegationClient,
    DelegationConnectError,
)

BEARER_TOKEN = "INTEGRATION_TEST_TOKEN_AT_LEAST_32_CHARS_X"
WRONG_BEARER_TOKEN = "WRONG_TOKEN_AT_LEAST_32_CHARS_XXXXXXXXX"
TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})

CliCommandFactory = Callable[[str], list[str]]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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
    app = build_gemini_app(
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
def gemini_server_happy_path() -> Iterator[tuple[str, int, str]]:
    host, port, thread, server = _start_server(
        cli_command_factory=_fake_factory("happy_path"),
        task_timeout_seconds=30.0,
    )
    try:
        yield host, port, BEARER_TOKEN
    finally:
        _stop_server(thread, server)


@pytest.fixture
def gemini_server_hanging() -> Iterator[tuple[str, int, str]]:
    host, port, thread, server = _start_server(
        cli_command_factory=_fake_factory("timeout"),
        task_timeout_seconds=60.0,
    )
    try:
        yield host, port, BEARER_TOKEN
    finally:
        _stop_server(thread, server)


@pytest_asyncio.fixture
async def gemini_server_real() -> AsyncIterator[tuple[str, int, str]]:
    host, port, thread, server = _start_server(
        cli_command_factory=gemini_command_factory,
        task_timeout_seconds=60.0,
    )
    try:
        yield host, port, BEARER_TOKEN
    finally:
        _stop_server(thread, server)


async def _collect_until_terminal(
    client: DelegationClient, prompt: str, *, deadline_seconds: float
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []

    async def _drain() -> None:
        async for event in client.delegate(prompt):
            events.append(event)
            data = event.get("data") or {}
            if (
                event.get("event") == "task.state"
                and isinstance(data, dict)
                and data.get("state") in TERMINAL_STATES
            ):
                return

    await asyncio.wait_for(_drain(), timeout=deadline_seconds)
    return events


def _state_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for event in events:
        if event.get("event") == "task.state":
            data = event.get("data")
            if isinstance(data, dict):
                out.append(data)
    return out


def _artifact_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for event in events:
        if event.get("event") == "task.artifact":
            data = event.get("data")
            if isinstance(data, dict):
                out.append(data)
    return out


async def test_p1_happy_path_delegation_streams_artifact_within_budget(
    gemini_server_happy_path: tuple[str, int, str],
) -> None:
    host, port, token = gemini_server_happy_path
    client = DelegationClient(
        peer_url=f"http://{host}:{port}",
        peer_bearer_token=token,
        timeout_seconds=10.0,
    )

    started = time.monotonic()
    events = await _collect_until_terminal(client, "ping", deadline_seconds=10.0)
    elapsed = time.monotonic() - started

    states = [payload["state"] for payload in _state_events(events)]
    artifacts = _artifact_events(events)
    assert "submitted" in states
    assert "working" in states
    assert states[-1] == "completed"
    assert artifacts, "expected at least one task.artifact event"
    first_artifact = artifacts[0]["artifact"]
    assert isinstance(first_artifact, dict)
    assert isinstance(first_artifact.get("content"), str)
    assert first_artifact["content"] != ""
    assert elapsed < 10.0


async def test_p1_peer_unreachable_raises_delegation_connect_error() -> None:
    dead_port = _free_port()
    client = DelegationClient(
        peer_url=f"http://127.0.0.1:{dead_port}",
        peer_bearer_token=BEARER_TOKEN,
        timeout_seconds=5.0,
    )

    started = time.monotonic()
    with pytest.raises(DelegationConnectError):
        async for _ in client.delegate("ping"):
            pass
    elapsed = time.monotonic() - started

    assert elapsed < 5.0


async def test_p1_wrong_bearer_token_raises_delegation_auth_error(
    gemini_server_happy_path: tuple[str, int, str],
) -> None:
    host, port, _ = gemini_server_happy_path
    client = DelegationClient(
        peer_url=f"http://{host}:{port}",
        peer_bearer_token=WRONG_BEARER_TOKEN,
        timeout_seconds=5.0,
    )

    started = time.monotonic()
    with pytest.raises(DelegationAuthError):
        async for _ in client.delegate("ping"):
            pass
    elapsed = time.monotonic() - started

    assert elapsed < 5.0


async def _consume_sse_lines(
    response: httpx.Response,
    on_event: Callable[[str, dict[str, object]], bool],
) -> None:
    pending_event: str | None = None
    pending_data: list[str] = []
    async for line in response.aiter_lines():
        if line == "":
            if pending_event is not None and pending_data:
                payload = json.loads("\n".join(pending_data))
                if on_event(pending_event, payload):
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


async def test_p1_cancel_while_working_emits_client_cancelled_terminal(
    gemini_server_hanging: tuple[str, int, str],
) -> None:
    host, port, token = gemini_server_hanging
    base_url = f"http://{host}:{port}"
    headers = {"Authorization": f"Bearer {token}"}
    send_body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tasks/sendSubscribe",
        "params": {"task": {"messages": [{"role": "user", "content": "hang"}]}},
    }

    timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
    cancel_envelope: dict[str, object] | None = None
    terminal_payload: dict[str, object] | None = None
    task_id_holder: dict[str, str] = {}
    cancel_sent_at: dict[str, float] = {}

    async with httpx.AsyncClient(timeout=timeout) as http:
        async with http.stream(
            "POST", f"{base_url}/jsonrpc", json=send_body, headers=headers
        ) as stream_response:
            assert stream_response.status_code == 200

            async def _handle_stream() -> None:
                nonlocal terminal_payload

                def _on_event(name: str, payload: dict[str, object]) -> bool:
                    nonlocal terminal_payload
                    if name != "task.state":
                        return False
                    state = payload.get("state")
                    if "task_id" not in task_id_holder and isinstance(
                        payload.get("task_id"), str
                    ):
                        task_id_holder["task_id"] = payload["task_id"]  # type: ignore[assignment]
                    if state == "working" and "cancel_trigger" not in cancel_sent_at:
                        cancel_sent_at["cancel_trigger"] = time.monotonic()
                    if state in TERMINAL_STATES:
                        terminal_payload = payload
                        return True
                    return False

                await _consume_sse_lines(stream_response, _on_event)

            async def _send_cancel_when_working() -> None:
                nonlocal cancel_envelope
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline:
                    if "cancel_trigger" in cancel_sent_at and "task_id" in task_id_holder:
                        break
                    await asyncio.sleep(0.05)
                else:
                    raise AssertionError(
                        "stream never reached working state within 5s"
                    )

                cancel_body = {
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": "tasks/cancel",
                    "params": {"task_id": task_id_holder["task_id"]},
                }
                response = await http.post(
                    f"{base_url}/jsonrpc", json=cancel_body, headers=headers
                )
                assert response.status_code == 200
                cancel_envelope = response.json()
                cancel_sent_at["sent_at"] = time.monotonic()

            await asyncio.wait_for(
                asyncio.gather(_handle_stream(), _send_cancel_when_working()),
                timeout=10.0,
            )

    assert cancel_envelope is not None
    result = cancel_envelope.get("result")
    assert isinstance(result, dict)
    assert result.get("state") == "cancelled"
    assert isinstance(result.get("cancelled_at"), str)
    assert result["cancelled_at"] != ""

    assert terminal_payload is not None
    assert terminal_payload.get("state") == "cancelled"
    assert terminal_payload.get("reason") == "client_cancelled"

    sent_at = cancel_sent_at.get("sent_at")
    assert sent_at is not None
    assert time.monotonic() - sent_at < 5.0


@pytest.mark.skipif(
    shutil.which("gemini") is None or not os.environ.get("GEMINI_API_KEY"),
    reason=(
        "gemini CLI not installed OR GEMINI_API_KEY not set; spec-conformance "
        "test runs only when both are present (auth required for real model calls)"
    ),
)
async def test_p1_real_gemini_delegation_completes_within_budget(
    gemini_server_real: tuple[str, int, str],
) -> None:
    host, port, token = gemini_server_real
    client = DelegationClient(
        peer_url=f"http://{host}:{port}",
        peer_bearer_token=token,
        timeout_seconds=60.0,
    )

    started = time.monotonic()
    events = await _collect_until_terminal(
        client, "Reply with the single word: pong", deadline_seconds=60.0
    )
    elapsed = time.monotonic() - started

    states = [payload["state"] for payload in _state_events(events)]
    artifacts = _artifact_events(events)
    assert states[-1] == "completed", f"expected completed terminal state, got {states}"
    assert artifacts, "expected at least one task.artifact event from real gemini"
    combined = "".join(
        str(a["artifact"].get("content", ""))
        for a in artifacts
        if isinstance(a.get("artifact"), dict)
    )
    assert "pong" in combined.lower()
    assert elapsed < 60.0
