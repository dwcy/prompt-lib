"""Contract tests for ``tasks/sendSubscribe`` (T022).

Pins the JSON-RPC and SSE wire contract for the streaming submit method per
``contracts/jsonrpc-methods.md`` and ``contracts/sse-events.md``: the request
shape and validation rules, the mandatory ``submitted -> working ->
{completed | failed | cancelled}`` event ordering, and the failure-mode
payloads (``cli_nonzero_exit``, ``cli_malformed_output``, ``timeout``).

Real CLI subprocess behaviour is the primary thing this batch must get right,
so the tests drive a CLI-agnostic runner via a deterministic fake CLI
(``tests.fixtures.fake_cli``) — they MUST NOT depend on ``gemini`` or
``claude`` being installed.

Per Constitution Principle III, this file lands BEFORE its implementation
(T025/T026). Until then every test is expected to fail with ImportError on
``a2a_bridge.protocol.cli_runner`` and
``a2a_bridge.adapters.gemini.server``.
"""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator, Callable

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

BEARER_TOKEN = "SECRET_TOKEN_12345_DO_NOT_LOG_AND_AT_LEAST_32_CHARS"

CliCommandFactory = Callable[[str], list[str]]


def _fake_factory(case: str, *, delay_ms: int = 0) -> CliCommandFactory:
    def factory(prompt: str) -> list[str]:
        return [
            sys.executable,
            "-m",
            "tests.fixtures.fake_cli",
            "--case",
            case,
            "--delay-ms",
            str(delay_ms),
            "--prompt",
            prompt,
        ]

    return factory


def _build_app(
    case: str,
    *,
    delay_ms: int = 0,
    task_timeout_seconds: float = 30.0,
):
    from a2a_bridge.adapters.gemini.server import build_gemini_app

    return build_gemini_app(
        bearer_token=BEARER_TOKEN,
        cli_command_factory=_fake_factory(case, delay_ms=delay_ms),
        task_timeout_seconds=task_timeout_seconds,
    )


@pytest_asyncio.fixture
async def happy_client() -> AsyncIterator[AsyncClient]:
    app = _build_app("happy_path")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _valid_send_subscribe_body(prompt: str = "hi") -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": "r1",
        "method": "tasks/sendSubscribe",
        "params": {"task": {"messages": [{"role": "user", "content": prompt}]}},
    }


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {BEARER_TOKEN}"}


async def _collect_sse_events(
    client: AsyncClient,
    body: dict[str, object],
    *,
    timeout_seconds: float = 5.0,
) -> tuple[int, str, list[tuple[str, dict[str, object]]]]:
    events: list[tuple[str, dict[str, object]]] = []
    pending_event: str | None = None
    pending_data: list[str] = []

    async with client.stream(
        "POST",
        "/jsonrpc",
        json=body,
        headers=_auth_headers(),
        timeout=timeout_seconds,
    ) as response:
        status_code = response.status_code
        content_type = response.headers.get("content-type", "")

        if status_code != 200:
            body_bytes = await response.aread()
            return status_code, content_type, [("__http_body__", json.loads(body_bytes))]

        async for line in response.aiter_lines():
            if line == "":
                if pending_event is not None and pending_data:
                    payload = json.loads("\n".join(pending_data))
                    events.append((pending_event, payload))
                pending_event = None
                pending_data = []
                continue

            if line.startswith(":"):
                continue

            if line.startswith("event:"):
                pending_event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                pending_data.append(line[len("data:") :].lstrip())

    return status_code, content_type, events


# ---------------------------------------------------------------------------
# Happy path: full lifecycle with a streaming CLI
# ---------------------------------------------------------------------------


class TestSendSubscribeHappyPath:
    async def test_response_content_type_is_text_event_stream(
        self, happy_client: AsyncClient
    ):
        async with happy_client.stream(
            "POST",
            "/jsonrpc",
            json=_valid_send_subscribe_body(),
            headers=_auth_headers(),
            timeout=5.0,
        ) as response:
            assert response.status_code == 200
            content_type = response.headers.get("content-type", "")

        assert content_type.split(";", 1)[0].strip().lower() == "text/event-stream"

    async def test_first_event_is_task_state_submitted(self, happy_client: AsyncClient):
        _, _, events = await _collect_sse_events(happy_client, _valid_send_subscribe_body())

        assert events, "expected at least one SSE event"
        first_name, first_payload = events[0]
        assert first_name == "task.state"
        assert first_payload["state"] == "submitted"

    async def test_submitted_then_working_then_terminal_completed(
        self, happy_client: AsyncClient
    ):
        _, _, events = await _collect_sse_events(happy_client, _valid_send_subscribe_body())

        states = [payload["state"] for name, payload in events if name == "task.state"]
        assert states[0] == "submitted"
        assert states[1] == "working"
        assert states[-1] == "completed"

    async def test_at_least_one_artifact_event_emitted_before_terminal(
        self, happy_client: AsyncClient
    ):
        _, _, events = await _collect_sse_events(happy_client, _valid_send_subscribe_body())

        terminal_index = next(
            i
            for i, (name, payload) in enumerate(events)
            if name == "task.state" and payload["state"] in {"completed", "failed", "cancelled"}
        )
        artifact_events = [name for name, _ in events[:terminal_index] if name == "task.artifact"]
        assert len(artifact_events) >= 1

    async def test_stream_closes_cleanly_within_five_seconds(
        self, happy_client: AsyncClient
    ):
        status_code, _, events = await _collect_sse_events(
            happy_client, _valid_send_subscribe_body(), timeout_seconds=5.0
        )

        assert status_code == 200
        assert events
        terminal_states = {"completed", "failed", "cancelled"}
        last_name, last_payload = events[-1]
        assert last_name == "task.state"
        assert last_payload["state"] in terminal_states


# ---------------------------------------------------------------------------
# Validation: invalid params return JSON-RPC -32602
# ---------------------------------------------------------------------------


class TestSendSubscribeValidation:
    async def _post_envelope(
        self, client: AsyncClient, params: dict[str, object]
    ) -> dict[str, object]:
        response = await client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": "r1",
                "method": "tasks/sendSubscribe",
                "params": params,
            },
            headers=_auth_headers(),
        )
        assert response.status_code == 200
        return response.json()

    async def test_empty_messages_array_returns_invalid_params(
        self, happy_client: AsyncClient
    ):
        envelope = await self._post_envelope(happy_client, {"task": {"messages": []}})

        assert envelope["error"]["code"] == -32602

    async def test_first_message_role_not_user_returns_invalid_params(
        self, happy_client: AsyncClient
    ):
        envelope = await self._post_envelope(
            happy_client,
            {"task": {"messages": [{"role": "assistant", "content": "hi"}]}},
        )

        assert envelope["error"]["code"] == -32602

    async def test_first_message_content_empty_returns_invalid_params(
        self, happy_client: AsyncClient
    ):
        envelope = await self._post_envelope(
            happy_client,
            {"task": {"messages": [{"role": "user", "content": ""}]}},
        )

        assert envelope["error"]["code"] == -32602


# ---------------------------------------------------------------------------
# CLI failure modes
# ---------------------------------------------------------------------------


class TestSendSubscribeCliFailures:
    async def test_nonzero_exit_terminates_with_failed_and_exit_code(self):
        app = _build_app("nonzero_exit")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            _, _, events = await _collect_sse_events(client, _valid_send_subscribe_body())

        last_name, last_payload = events[-1]
        assert last_name == "task.state"
        assert last_payload["state"] == "failed"
        assert last_payload["reason"] == "cli_nonzero_exit"
        assert last_payload.get("exit_code") == 2
        assert "boom" in (last_payload.get("stderr_tail") or "")

    async def test_malformed_cli_output_terminates_with_failed_and_reason(self):
        app = _build_app("malformed")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            _, _, events = await _collect_sse_events(client, _valid_send_subscribe_body())

        last_name, last_payload = events[-1]
        assert last_name == "task.state"
        assert last_payload["state"] == "failed"
        assert last_payload["reason"] == "cli_malformed_output"

    async def test_per_task_timeout_cancels_within_two_seconds(self):
        app = _build_app("timeout", task_timeout_seconds=1.0)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            status_code, _, events = await _collect_sse_events(
                client, _valid_send_subscribe_body(), timeout_seconds=2.0
            )

        assert status_code == 200
        last_name, last_payload = events[-1]
        assert last_name == "task.state"
        assert last_payload["state"] == "cancelled"
        assert last_payload["reason"] == "timeout"


@pytest.mark.parametrize(
    "params",
    [
        {"task": {"messages": []}},
        {"task": {"messages": [{"role": "assistant", "content": "x"}]}},
        {"task": {"messages": [{"role": "user", "content": ""}]}},
    ],
    ids=["empty-messages", "wrong-role", "empty-content"],
)
async def test_invalid_params_never_open_sse_stream(
    happy_client: AsyncClient, params: dict[str, object]
):
    response = await happy_client.post(
        "/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "id": "r1",
            "method": "tasks/sendSubscribe",
            "params": params,
        },
        headers=_auth_headers(),
    )

    content_type = response.headers.get("content-type", "")
    assert content_type.split(";", 1)[0].strip().lower() != "text/event-stream"
