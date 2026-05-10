"""Contract tests for ``tasks/get`` (T023).

Pins the JSON-RPC contract for status polling per
``contracts/jsonrpc-methods.md``: a successful lookup returns the current
``state`` and accumulated ``artifacts``; an unknown ``task_id`` returns
``-32602`` with ``data.reason == "task_not_found"``.

The tests drive a CLI-agnostic runner via the deterministic
``tests.fixtures.fake_cli`` fake — they MUST NOT depend on ``gemini`` or
``claude`` being installed.

Per Constitution Principle III, this file lands BEFORE its implementation
(T025/T026). Until then every test is expected to fail with ImportError on
``a2a_bridge.protocol.cli_runner`` and
``a2a_bridge.adapters.gemini.server``.
"""

from __future__ import annotations

import json
import sys
import uuid
from collections.abc import AsyncIterator, Callable

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


def _build_app(case: str):
    from a2a_bridge.adapters.gemini.server import build_gemini_app

    return build_gemini_app(
        bearer_token=BEARER_TOKEN,
        cli_command_factory=_fake_factory(case),
        task_timeout_seconds=30.0,
    )


@pytest_asyncio.fixture
async def happy_client() -> AsyncIterator[AsyncClient]:
    app = _build_app("happy_path")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {BEARER_TOKEN}"}


async def _send_subscribe_until_terminal(
    client: AsyncClient, prompt: str = "hi", *, timeout_seconds: float = 5.0
) -> str:
    body = {
        "jsonrpc": "2.0",
        "id": "r-send",
        "method": "tasks/sendSubscribe",
        "params": {"task": {"messages": [{"role": "user", "content": prompt}]}},
    }

    task_id: str | None = None
    pending_event: str | None = None
    pending_data: list[str] = []
    terminal_states = {"completed", "failed", "cancelled"}

    async with client.stream(
        "POST",
        "/jsonrpc",
        json=body,
        headers=_auth_headers(),
        timeout=timeout_seconds,
    ) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line == "":
                if pending_event is not None and pending_data:
                    payload = json.loads("\n".join(pending_data))
                    if pending_event == "task.state":
                        if task_id is None:
                            task_id = payload["task_id"]
                        if payload["state"] in terminal_states:
                            pending_event = None
                            pending_data = []
                            break
                pending_event = None
                pending_data = []
                continue

            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                pending_event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                pending_data.append(line[len("data:") :].lstrip())

    assert task_id is not None, "no task_id was observed in the SSE stream"
    return task_id


async def _post_get(client: AsyncClient, task_id: str) -> dict[str, object]:
    response = await client.post(
        "/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "id": "r-get",
            "method": "tasks/get",
            "params": {"task_id": task_id},
        },
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    return response.json()


# ---------------------------------------------------------------------------
# Happy path: get after completion returns full task record with artifacts
# ---------------------------------------------------------------------------


class TestGetAfterCompletion:
    async def test_state_is_completed(self, happy_client: AsyncClient):
        task_id = await _send_subscribe_until_terminal(happy_client)

        envelope = await _post_get(happy_client, task_id)

        assert envelope["result"]["state"] == "completed"

    async def test_task_id_is_echoed(self, happy_client: AsyncClient):
        task_id = await _send_subscribe_until_terminal(happy_client)

        envelope = await _post_get(happy_client, task_id)

        assert envelope["result"]["task_id"] == task_id

    async def test_artifacts_is_a_non_empty_list(self, happy_client: AsyncClient):
        task_id = await _send_subscribe_until_terminal(happy_client)

        envelope = await _post_get(happy_client, task_id)

        artifacts = envelope["result"]["artifacts"]
        assert isinstance(artifacts, list)
        assert len(artifacts) >= 1

    async def test_artifact_carries_text_payload(self, happy_client: AsyncClient):
        task_id = await _send_subscribe_until_terminal(happy_client)

        envelope = await _post_get(happy_client, task_id)

        artifact = envelope["result"]["artifacts"][0]
        assert artifact["kind"] == "text"
        assert isinstance(artifact["content"], str)
        assert artifact["content"] != ""


# ---------------------------------------------------------------------------
# Unknown task_id: -32602 with structured reason
# ---------------------------------------------------------------------------


class TestGetUnknownTaskId:
    async def test_unknown_task_id_returns_invalid_params(
        self, happy_client: AsyncClient
    ):
        envelope = await _post_get(happy_client, str(uuid.uuid4()))

        assert envelope["error"]["code"] == -32602

    async def test_unknown_task_id_data_reason_is_task_not_found(
        self, happy_client: AsyncClient
    ):
        envelope = await _post_get(happy_client, str(uuid.uuid4()))

        assert envelope["error"]["data"]["reason"] == "task_not_found"
