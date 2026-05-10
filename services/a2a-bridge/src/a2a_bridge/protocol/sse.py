"""SSE event helpers and ordering enforcer (T019).

Implements the framing and ordering rules in ``contracts/sse-events.md``:
the only event names emitted are ``task.state``, ``task.artifact``, and
``task.progress``; every formatted frame ends with exactly one blank line;
the first event of a stream is always ``task.state: submitted``; the last
event is always a terminal ``task.state``; and after a terminal state no
further events may be emitted on the same stream.

The ``OrderingEnforcer`` is a pure-Python state machine that runs alongside
the SSE producer in tests and (optionally) in production to fail fast if a
producer ever emits an out-of-spec sequence.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class TaskStateEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    state: Literal["submitted", "working", "completed", "failed", "cancelled"]
    ts: str
    reason: str | None = None
    exit_code: int | None = None
    stderr_tail: str | None = None


class TaskArtifactEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    artifact: dict[str, Any]


class TaskProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    message: str
    ts: str


_EVENT_NAMES: dict[type, str] = {
    TaskStateEvent: "task.state",
    TaskArtifactEvent: "task.artifact",
    TaskProgressEvent: "task.progress",
}

_TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})


class OrderingViolation(Exception):
    """Raised when the SSE event stream violates the documented ordering rules."""


def format_event(event: TaskStateEvent | TaskArtifactEvent | TaskProgressEvent) -> str:
    event_name = _EVENT_NAMES[type(event)]
    payload = event.model_dump(mode="json", exclude_none=True)
    return f"event: {event_name}\ndata: {_dump_json(payload)}\n\n"


def _dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"))


class OrderingEnforcer:
    def __init__(self, task_id: str) -> None:
        self._task_id = task_id
        self._current_state: str | None = None
        self._terminated = False

    def check(
        self,
        event: TaskStateEvent | TaskArtifactEvent | TaskProgressEvent,
    ) -> None:
        if event.task_id != self._task_id:
            raise OrderingViolation(
                f"event task_id {event.task_id!r} does not match stream task_id "
                f"{self._task_id!r}"
            )

        if self._terminated:
            raise OrderingViolation(
                f"no events allowed after terminal state {self._current_state!r}"
            )

        if isinstance(event, TaskStateEvent):
            self._check_state_event(event)
            return

        if self._current_state != "working":
            raise OrderingViolation(
                f"{_EVENT_NAMES[type(event)]!r} only allowed after task.state: working "
                f"(current state: {self._current_state!r})"
            )

    def _check_state_event(self, event: TaskStateEvent) -> None:
        new_state = event.state

        if self._current_state is None:
            if new_state != "submitted":
                raise OrderingViolation(
                    f"first event must be task.state: submitted (got {new_state!r})"
                )
            self._current_state = new_state
            return

        if new_state == self._current_state:
            raise OrderingViolation(
                f"task.state: {new_state!r} repeats current state"
            )

        if self._current_state == "submitted":
            if new_state not in {"working", "cancelled"}:
                raise OrderingViolation(
                    f"from submitted, only working or cancelled allowed (got {new_state!r})"
                )
        elif self._current_state == "working":
            if new_state not in _TERMINAL_STATES:
                raise OrderingViolation(
                    f"from working, only a terminal state allowed (got {new_state!r})"
                )
        else:
            raise OrderingViolation(
                f"unexpected transition from {self._current_state!r} to {new_state!r}"
            )

        self._current_state = new_state
        if new_state in _TERMINAL_STATES:
            self._terminated = True
