"""Concurrency integration test for the Claude adapter (T037).

Proves spec.md SC-007 — "Concurrent inbound tasks (at least 3 in flight)
complete independently, each producing its own correct artifact, with no
cross-contamination of CLI state" — and the supporting edge case "Two
inbound tasks arrive simultaneously".

Strategy: run a real Claude adapter in a uvicorn thread (same fixture shape
as ``test_p2_inbound_curl.py``) and fire multiple ``tasks/sendSubscribe``
requests in parallel via :func:`asyncio.gather`. Each request carries a
unique prompt; the fake CLI echoes the prompt back inside an ``assistant``
text block so cross-contamination would be visible as a sibling's prompt
text appearing in a task's artifact. ``ASGITransport`` cannot be used here
because it buffers the entire SSE response, which would serialize what is
meant to be tested as concurrent.

Coverage:

1. Three parallel ``tasks/sendSubscribe`` calls each complete with a
   ``task.artifact`` whose content echoes its OWN prompt and contains no
   sibling prompt text — proves per-task CLI isolation under load.
2. Five parallel calls produce five distinct task UUIDs — proves the
   :class:`Adapter.tasks` registry never collides or aliases task ids.
3. A long-running task can be polled via ``tasks/get`` while in flight and
   reports ``state == "working"``; the original SSE stream still completes
   afterwards — proves the per-task lifecycle is observable concurrently
   with other JSON-RPC traffic on the same adapter.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
import threading
import time
import uuid
from collections.abc import Callable, Iterator

import httpx
import pytest
import uvicorn

from a2a_bridge.adapters.claude.server import build_claude_app

BEARER_TOKEN = "INTEGRATION_TEST_TOKEN_AT_LEAST_32_CHARS_X"
TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})

CliCommandFactory = Callable[[str], list[str]]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


_ECHO_SCRIPT = (
    "import json,sys;"
    "p=sys.argv[1];"
    'print(json.dumps({"type":"system","subtype":"init"}),flush=True);'
    "print(json.dumps({"
    '"type":"assistant",'
    '"message":{"role":"assistant",'
    '"content":[{"type":"text","text":f"echo:{p}"}]}'
    "}),flush=True);"
    'print(json.dumps({"type":"result","subtype":"success"}),flush=True)'
)


_SLOW_ECHO_SCRIPT = (
    "import json,sys,time;"
    "p=sys.argv[1];"
    'print(json.dumps({"type":"system","subtype":"init"}),flush=True);'
    "time.sleep(3.0);"
    "print(json.dumps({"
    '"type":"assistant",'
    '"message":{"role":"assistant",'
    '"content":[{"type":"text","text":f"echo:{p}"}]}'
    "}),flush=True);"
    'print(json.dumps({"type":"result","subtype":"success"}),flush=True)'
)


def _echo_factory() -> CliCommandFactory:
    def factory(prompt: str) -> list[str]:
        return [sys.executable, "-c", _ECHO_SCRIPT, prompt]

    return factory


def _slow_echo_factory() -> CliCommandFactory:
    def factory(prompt: str) -> list[str]:
        return [sys.executable, "-c", _SLOW_ECHO_SCRIPT, prompt]

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
def claude_server_echo() -> Iterator[tuple[str, int, str]]:
    host, port, thread, server = _start_server(
        cli_command_factory=_echo_factory(),
        task_timeout_seconds=30.0,
    )
    try:
        yield host, port, BEARER_TOKEN
    finally:
        _stop_server(thread, server)


@pytest.fixture
def claude_server_slow_echo() -> Iterator[tuple[str, int, str]]:
    host, port, thread, server = _start_server(
        cli_command_factory=_slow_echo_factory(),
        task_timeout_seconds=30.0,
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


async def _run_one_send_subscribe(
    base_url: str, headers: dict[str, str], prompt: str, *, deadline_seconds: float
) -> tuple[str, list[tuple[str, dict[str, object]]]]:
    timeout = httpx.Timeout(connect=5.0, read=deadline_seconds, write=5.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST", f"{base_url}/jsonrpc", json=_send_subscribe_body(prompt), headers=headers
        ) as response:
            assert response.status_code == 200
            events = await _drain_sse_until_terminal(
                response, deadline_seconds=deadline_seconds
            )
    return prompt, events


async def test_concurrent_3_tasks_each_produces_own_artifact(
    claude_server_echo: tuple[str, int, str],
) -> None:
    host, port, token = claude_server_echo
    base_url = f"http://{host}:{port}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    prompts = ["task-001", "task-002", "task-003"]

    started = time.monotonic()
    results = await asyncio.wait_for(
        asyncio.gather(
            *(
                _run_one_send_subscribe(base_url, headers, prompt, deadline_seconds=10.0)
                for prompt in prompts
            )
        ),
        timeout=10.0,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 10.0, f"3 concurrent tasks took {elapsed:.2f}s, exceeds 10s budget"
    assert {prompt for prompt, _ in results} == set(prompts)

    for prompt, events in results:
        states = [payload for name, payload in events if name == "task.state"]
        artifacts = [payload for name, payload in events if name == "task.artifact"]
        assert states, f"task {prompt!r}: expected at least one task.state event"
        assert states[-1].get("state") == "completed", (
            f"task {prompt!r}: expected completed terminal state, "
            f"got {[s.get('state') for s in states]}"
        )
        assert artifacts, f"task {prompt!r}: expected at least one task.artifact event"
        artifact = artifacts[0].get("artifact")
        assert isinstance(artifact, dict)
        content = artifact.get("content")
        assert isinstance(content, str)
        assert content == f"echo:{prompt}", (
            f"task {prompt!r}: artifact content {content!r} did not echo own prompt"
        )
        for sibling in prompts:
            if sibling == prompt:
                continue
            assert sibling not in content, (
                f"task {prompt!r}: artifact content {content!r} contains "
                f"sibling prompt {sibling!r} — cross-contamination of CLI state"
            )


async def test_concurrent_5_tasks_have_distinct_task_ids(
    claude_server_echo: tuple[str, int, str],
) -> None:
    host, port, token = claude_server_echo
    base_url = f"http://{host}:{port}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    prompts = [f"distinct-{i:03d}" for i in range(5)]

    results = await asyncio.wait_for(
        asyncio.gather(
            *(
                _run_one_send_subscribe(base_url, headers, prompt, deadline_seconds=10.0)
                for prompt in prompts
            )
        ),
        timeout=10.0,
    )

    task_ids: list[str] = []
    for prompt, events in results:
        submitted = next(
            (
                payload
                for name, payload in events
                if name == "task.state" and payload.get("state") == "submitted"
            ),
            None,
        )
        assert submitted is not None, (
            f"task {prompt!r}: never observed task.state: submitted event"
        )
        task_id = submitted.get("task_id")
        assert isinstance(task_id, str)
        uuid.UUID(task_id)
        task_ids.append(task_id)

    assert len(set(task_ids)) == len(task_ids), (
        f"task_ids collided across concurrent streams: {task_ids}"
    )


async def test_concurrent_get_during_inflight_returns_working_state(
    claude_server_slow_echo: tuple[str, int, str],
) -> None:
    host, port, token = claude_server_slow_echo
    base_url = f"http://{host}:{port}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    captured_task_id: dict[str, str] = {}
    inflight_get_state: dict[str, object] = {}
    timeout = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)

    async def _stream_long_task() -> list[tuple[str, dict[str, object]]]:
        async with httpx.AsyncClient(timeout=timeout) as stream_client:
            async with stream_client.stream(
                "POST",
                f"{base_url}/jsonrpc",
                json=_send_subscribe_body("slow-echo-1"),
                headers=headers,
            ) as response:
                assert response.status_code == 200
                events: list[tuple[str, dict[str, object]]] = []
                pending_event: str | None = None
                pending_data: list[str] = []
                async for line in response.aiter_lines():
                    if line == "":
                        if pending_event is not None and pending_data:
                            payload = json.loads("\n".join(pending_data))
                            events.append((pending_event, payload))
                            if pending_event == "task.state":
                                if (
                                    "task_id" not in captured_task_id
                                    and isinstance(payload.get("task_id"), str)
                                ):
                                    captured_task_id["task_id"] = payload["task_id"]  # type: ignore[assignment]
                                state = payload.get("state")
                                if isinstance(state, str) and state in TERMINAL_STATES:
                                    return events
                        pending_event = None
                        pending_data = []
                        continue
                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        pending_event = line[len("event:") :].strip()
                    elif line.startswith("data:"):
                        pending_data.append(line[len("data:") :].lstrip())
                return events

    async def _poll_get_while_working() -> None:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if "task_id" in captured_task_id:
                break
            await asyncio.sleep(0.02)
        else:
            raise AssertionError("never captured task_id from inflight stream")

        await asyncio.sleep(0.5)

        async with httpx.AsyncClient(timeout=timeout) as get_client:
            response = await get_client.post(
                f"{base_url}/jsonrpc",
                json={
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": "tasks/get",
                    "params": {"task_id": captured_task_id["task_id"]},
                },
                headers=headers,
            )
        assert response.status_code == 200
        envelope = response.json()
        result = envelope.get("result")
        assert isinstance(result, dict)
        inflight_get_state["state"] = result.get("state")
        inflight_get_state["task_id"] = result.get("task_id")

    started = time.monotonic()
    stream_events, _ = await asyncio.wait_for(
        asyncio.gather(_stream_long_task(), _poll_get_while_working()),
        timeout=15.0,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 15.0
    assert inflight_get_state.get("state") == "working", (
        f"tasks/get during in-flight task returned state "
        f"{inflight_get_state.get('state')!r}, expected 'working'"
    )
    assert inflight_get_state.get("task_id") == captured_task_id["task_id"]

    states = [payload for name, payload in stream_events if name == "task.state"]
    assert states, "expected at least one task.state event from the slow stream"
    assert states[-1].get("state") == "completed", (
        f"slow stream did not complete cleanly after concurrent get; "
        f"final state was {states[-1].get('state')!r}"
    )
    artifacts = [payload for name, payload in stream_events if name == "task.artifact"]
    assert artifacts, "expected at least one task.artifact from the slow stream"
    artifact = artifacts[0].get("artifact")
    assert isinstance(artifact, dict)
    assert artifact.get("content") == "echo:slow-echo-1"
