"""Contract tests for ``tasks/cancel`` (T024).

Pins the JSON-RPC contract for explicit cancellation per
``contracts/jsonrpc-methods.md``: cancelling a working task transitions it
to ``cancelled`` and emits a final ``task.state`` event with
``reason: "client_cancelled"`` on the original SSE stream; cancelling a
task that has already reached a terminal state returns ``-32602`` with
``data.reason == "task_already_terminal"`` and the current ``state``.

Real CLI subprocess behaviour is the primary thing this batch must get right,
so the tests drive a CLI-agnostic runner via the deterministic
``tests.fixtures.fake_cli`` fake — they MUST NOT depend on ``gemini`` or
``claude`` being installed.

Per Constitution Principle III, this file lands BEFORE its implementation
(T025/T026). Until then every test is expected to fail with ImportError on
``a2a_bridge.protocol.cli_runner`` and
``a2a_bridge.adapters.gemini.server``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator, Callable

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

BEARER_TOKEN = "SECRET_TOKEN_12345_DO_NOT_LOG_AND_AT_LEAST_32_CHARS"

CliCommandFactory = Callable[[str], list[str]]


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


def _build_app(case: str, *, task_timeout_seconds: float = 30.0):
    from a2a_bridge.adapters.gemini.server import build_gemini_app

    return build_gemini_app(
        bearer_token=BEARER_TOKEN,
        cli_command_factory=_fake_factory(case),
        task_timeout_seconds=task_timeout_seconds,
    )


@pytest_asyncio.fixture
async def hanging_client() -> AsyncIterator[AsyncClient]:
    app = _build_app("timeout", task_timeout_seconds=30.0)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def happy_client() -> AsyncIterator[AsyncClient]:
    app = _build_app("happy_path")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {BEARER_TOKEN}"}


def _send_subscribe_body(prompt: str = "hi") -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": "r-send",
        "method": "tasks/sendSubscribe",
        "params": {"task": {"messages": [{"role": "user", "content": prompt}]}},
    }


async def _post_cancel(client: AsyncClient, task_id: str) -> dict[str, object]:
    response = await client.post(
        "/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "id": "r-cancel",
            "method": "tasks/cancel",
            "params": {"task_id": task_id},
        },
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    return response.json()


async def _consume_stream_until_terminal(
    response, *, timeout_seconds: float = 5.0
) -> tuple[str, list[tuple[str, dict[str, object]]]]:
    events: list[tuple[str, dict[str, object]]] = []
    pending_event: str | None = None
    pending_data: list[str] = []
    task_id: str | None = None
    terminal_states = {"completed", "failed", "cancelled"}

    async def _drain() -> None:
        nonlocal pending_event, pending_data, task_id
        async for line in response.aiter_lines():
            if line == "":
                if pending_event is not None and pending_data:
                    payload = json.loads("\n".join(pending_data))
                    events.append((pending_event, payload))
                    if pending_event == "task.state":
                        if task_id is None:
                            task_id = payload["task_id"]
                        if payload["state"] in terminal_states:
                            pending_event = None
                            pending_data = []
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

    await asyncio.wait_for(_drain(), timeout=timeout_seconds)
    assert task_id is not None
    return task_id, events


async def _read_until_state(
    response, target_state: str, *, timeout_seconds: float = 2.0
) -> str:
    pending_event: str | None = None
    pending_data: list[str] = []
    task_id: str | None = None

    async def _drain() -> None:
        nonlocal pending_event, pending_data, task_id
        async for line in response.aiter_lines():
            if line == "":
                if pending_event is not None and pending_data:
                    payload = json.loads("\n".join(pending_data))
                    if pending_event == "task.state":
                        if task_id is None:
                            task_id = payload["task_id"]
                        if payload["state"] == target_state:
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

    await asyncio.wait_for(_drain(), timeout=timeout_seconds)
    assert task_id is not None
    return task_id


# ---------------------------------------------------------------------------
# Happy path: cancel a working task
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "Mid-stream cancel cannot be exercised via httpx.ASGITransport: it buffers the "
        "entire SSE response before yielding, so the tasks/cancel POST cannot be processed "
        "while the original stream is still working. The fake CLI's per-task timeout always "
        "fires first, transitioning the task to cancelled:timeout before the client cancel "
        "lands. Spec-compliant cancel-while-working is verified end-to-end in the T030 "
        "integration test (services/a2a-bridge/tests/integration/test_p1_outbound_delegation.py) "
        "against a real uvicorn server, which streams responses correctly."
    )
)
class TestCancelWorkingTask:
    async def test_cancel_response_state_is_cancelled(
        self, hanging_client: AsyncClient
    ):
        async with hanging_client.stream(
            "POST",
            "/jsonrpc",
            json=_send_subscribe_body(),
            headers=_auth_headers(),
            timeout=10.0,
        ) as stream_response:
            task_id = await _read_until_state(stream_response, "working")

            cancel_envelope = await _post_cancel(hanging_client, task_id)

            await asyncio.wait_for(stream_response.aclose(), timeout=5.0)

        assert cancel_envelope["result"]["state"] == "cancelled"

    async def test_cancel_response_includes_cancelled_at_timestamp(
        self, hanging_client: AsyncClient
    ):
        async with hanging_client.stream(
            "POST",
            "/jsonrpc",
            json=_send_subscribe_body(),
            headers=_auth_headers(),
            timeout=10.0,
        ) as stream_response:
            task_id = await _read_until_state(stream_response, "working")

            cancel_envelope = await _post_cancel(hanging_client, task_id)

            await asyncio.wait_for(stream_response.aclose(), timeout=5.0)

        assert isinstance(cancel_envelope["result"]["cancelled_at"], str)
        assert cancel_envelope["result"]["cancelled_at"] != ""

    async def test_original_stream_emits_terminal_cancelled_with_client_reason(
        self, hanging_client: AsyncClient
    ):
        terminal_payload: dict[str, object] | None = None

        async with hanging_client.stream(
            "POST",
            "/jsonrpc",
            json=_send_subscribe_body(),
            headers=_auth_headers(),
            timeout=10.0,
        ) as stream_response:
            task_id = await _read_until_state(stream_response, "working")

            await _post_cancel(hanging_client, task_id)

            pending_event: str | None = None
            pending_data: list[str] = []

            async def _drain_terminal() -> None:
                nonlocal pending_event, pending_data, terminal_payload
                async for line in stream_response.aiter_lines():
                    if line == "":
                        if pending_event is not None and pending_data:
                            payload = json.loads("\n".join(pending_data))
                            if pending_event == "task.state" and payload["state"] in {
                                "completed",
                                "failed",
                                "cancelled",
                            }:
                                terminal_payload = payload
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

            await asyncio.wait_for(_drain_terminal(), timeout=5.0)

        assert terminal_payload is not None
        assert terminal_payload["state"] == "cancelled"
        assert terminal_payload["reason"] == "client_cancelled"


# ---------------------------------------------------------------------------
# Already-terminal task: -32602 with structured reason and current state
# ---------------------------------------------------------------------------


class TestCancelAlreadyTerminal:
    async def test_cancel_after_completion_returns_invalid_params(
        self, happy_client: AsyncClient
    ):
        async with happy_client.stream(
            "POST",
            "/jsonrpc",
            json=_send_subscribe_body(),
            headers=_auth_headers(),
            timeout=5.0,
        ) as stream_response:
            task_id, _ = await _consume_stream_until_terminal(stream_response)

        envelope = await _post_cancel(happy_client, task_id)

        assert envelope["error"]["code"] == -32602

    async def test_cancel_after_completion_data_reason_is_task_already_terminal(
        self, happy_client: AsyncClient
    ):
        async with happy_client.stream(
            "POST",
            "/jsonrpc",
            json=_send_subscribe_body(),
            headers=_auth_headers(),
            timeout=5.0,
        ) as stream_response:
            task_id, _ = await _consume_stream_until_terminal(stream_response)

        envelope = await _post_cancel(happy_client, task_id)

        assert envelope["error"]["data"]["reason"] == "task_already_terminal"

    async def test_cancel_after_completion_data_state_is_completed(
        self, happy_client: AsyncClient
    ):
        async with happy_client.stream(
            "POST",
            "/jsonrpc",
            json=_send_subscribe_body(),
            headers=_auth_headers(),
            timeout=5.0,
        ) as stream_response:
            task_id, _ = await _consume_stream_until_terminal(stream_response)

        envelope = await _post_cancel(happy_client, task_id)

        assert envelope["error"]["data"]["state"] == "completed"
