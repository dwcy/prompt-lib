"""Gemini A2A adapter app factory (T026).

Wires the generic :class:`a2a_bridge.protocol.cli_runner.CliRunner` to the
Gemini-specific NDJSON parser and command factory, exposes the standard
``/.well-known/agent-card.json`` discovery document, and registers the three
JSON-RPC methods documented in ``contracts/jsonrpc-methods.md``:

* ``tasks/sendSubscribe`` — validates the request, creates a :class:`Task`,
  and streams ``task.state`` / ``task.artifact`` SSE events.
* ``tasks/get`` — returns the current state and accumulated artifacts for a
  known task; returns ``-32602`` with ``data.reason="task_not_found"`` for
  unknown ids.
* ``tasks/cancel`` — terminates a running task and emits a final
  ``cancelled`` SSE event with ``reason="client_cancelled"`` on the original
  stream; returns ``-32602`` with ``data.reason="task_already_terminal"``
  when the task is already in a terminal state.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from a2a_bridge.adapters.base import build_app
from a2a_bridge.adapters.gemini.runner import gemini_command_factory, parse_gemini_event
from a2a_bridge.protocol.agent_card import build_agent_card
from a2a_bridge.protocol.cli_runner import CliRunner
from a2a_bridge.protocol.jsonrpc import ErrorCode, JsonRpcError
from a2a_bridge.protocol.logging import log_task_received
from a2a_bridge.protocol.sse import OrderingEnforcer, format_event
from a2a_bridge.protocol.tasks import Task, TaskState

_AGENT_NAME = "gemini-a2a-adapter"
_SKILL_ID = "gemini-prompt"
_SSE_MEDIA_TYPE = "text/event-stream"
_TERMINAL_STATES = frozenset({TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED})


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _build_card(host: str, port: int):
    return build_agent_card(
        name=_AGENT_NAME,
        host=host,
        port=port,
        description="A2A bridge adapter that delegates prompts to the Gemini CLI.",
        skills=[
            {
                "id": _SKILL_ID,
                "name": "gemini-prompt",
                "description": "Forward a user prompt to the Gemini CLI and stream its output.",
                "input_modes": ["text/plain"],
                "output_modes": ["text/plain"],
            }
        ],
    )


def _extract_prompt(params: dict[str, Any] | list[Any] | None) -> str:
    if not isinstance(params, dict):
        raise JsonRpcError(
            ErrorCode.INVALID_PARAMS, "Invalid params", {"reason": "params_must_be_object"}
        )

    task_payload = params.get("task")
    if not isinstance(task_payload, dict):
        raise JsonRpcError(
            ErrorCode.INVALID_PARAMS, "Invalid params", {"missing": ["task"]}
        )

    messages = task_payload.get("messages")
    if not isinstance(messages, list) or len(messages) == 0:
        raise JsonRpcError(
            ErrorCode.INVALID_PARAMS,
            "Invalid params",
            {"reason": "messages_must_be_non_empty_array"},
        )

    first = messages[0]
    if not isinstance(first, dict):
        raise JsonRpcError(
            ErrorCode.INVALID_PARAMS,
            "Invalid params",
            {"reason": "first_message_must_be_object"},
        )

    if first.get("role") != "user":
        raise JsonRpcError(
            ErrorCode.INVALID_PARAMS,
            "Invalid params",
            {"reason": "first_message_role_must_be_user"},
        )

    content = first.get("content")
    if not isinstance(content, str) or content == "":
        raise JsonRpcError(
            ErrorCode.INVALID_PARAMS,
            "Invalid params",
            {"reason": "first_message_content_must_be_non_empty_string"},
        )

    return content


def _require_task(app: FastAPI, params: dict[str, Any] | list[Any] | None) -> Task:
    if not isinstance(params, dict):
        raise JsonRpcError(
            ErrorCode.INVALID_PARAMS, "Invalid params", {"reason": "params_must_be_object"}
        )
    task_id = params.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise JsonRpcError(
            ErrorCode.INVALID_PARAMS, "Invalid params", {"missing": ["task_id"]}
        )
    task = app.state.tasks.get(task_id)
    if task is None:
        raise JsonRpcError(
            ErrorCode.INVALID_PARAMS, "Invalid params", {"reason": "task_not_found"}
        )
    return task


def _artifact_payload(artifact: Any) -> dict[str, Any]:
    return artifact.model_dump(mode="json")


def build_gemini_app(
    *,
    bearer_token: str,
    cli_command_factory: Callable[[str], list[str]] = gemini_command_factory,
    task_timeout_seconds: float = 300.0,
    host: str = "127.0.0.1",
    port: int = 8766,
) -> FastAPI:
    card = _build_card(host=host, port=port)
    app = build_app(bearer_token=bearer_token, name=_AGENT_NAME, agent_card=card)

    app.state.tasks: dict[str, Task] = {}

    runner = CliRunner(
        cli_command_factory=cli_command_factory,
        parse_event=parse_gemini_event,
        task_timeout_seconds=task_timeout_seconds,
    )

    async def _stream_task(task: Task, prompt: str) -> AsyncIterator[bytes]:
        enforcer = OrderingEnforcer(task_id=str(task.id))
        async for event in runner.run(prompt, task):
            enforcer.check(event)
            frame = format_event(event)
            yield frame.encode("utf-8")

    def handle_send_subscribe(
        params: dict[str, Any] | list[Any] | None,
    ) -> StreamingResponse:
        prompt = _extract_prompt(params)
        task = Task(method="tasks/sendSubscribe", params=params, peer_identity="local")
        app.state.tasks[str(task.id)] = task
        log_task_received(task_id=str(task.id), peer="local")
        return StreamingResponse(
            _stream_task(task, prompt),
            media_type=_SSE_MEDIA_TYPE,
            headers={"Cache-Control": "no-store"},
        )

    def handle_get(params: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
        task = _require_task(app, params)
        return {
            "task_id": str(task.id),
            "state": task.state.value,
            "artifacts": [_artifact_payload(a) for a in task.artifacts],
            "created_at": task.created_at.isoformat().replace("+00:00", "Z"),
            "last_state_change_at": task.last_state_change_at.isoformat().replace(
                "+00:00", "Z"
            ),
        }

    def handle_cancel(params: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
        task = _require_task(app, params)
        if task.state in _TERMINAL_STATES:
            raise JsonRpcError(
                ErrorCode.INVALID_PARAMS,
                "Invalid params",
                {"reason": "task_already_terminal", "state": task.state.value},
            )
        task.transition(TaskState.CANCELLED)
        return {
            "task_id": str(task.id),
            "state": "cancelled",
            "cancelled_at": _now_iso(),
        }

    registry = app.state.method_registry
    registry["tasks/sendSubscribe"] = handle_send_subscribe
    registry["tasks/get"] = handle_get
    registry["tasks/cancel"] = handle_cancel

    return app
