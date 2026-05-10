"""Task entity, state machine, and per-task event queue (T015).

Implements the lifecycle invariants documented in ``data-model.md`` § Task:
the legal transition graph is ``submitted → working → {completed | failed |
cancelled}`` plus the early-cancel shortcut ``submitted → cancelled``;
terminal states are sticky; the per-task ``asyncio.Queue`` is closed (a
``None`` sentinel is pushed) on terminal transition; and the underlying
subprocess reference is reaped (``terminate()`` called, attribute cleared)
before the terminal transition is applied.

``Task`` is intentionally NOT a Pydantic model: it carries mutable runtime
state (subprocess handle, asyncio queue) that does not belong in a wire-
format schema. ``Artifact`` IS a Pydantic v2 model — it serializes straight
into ``task.artifact`` SSE payloads.
"""

from __future__ import annotations

import asyncio
import subprocess
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskState(StrEnum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_TERMINAL_STATES = frozenset({TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED})

_ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.SUBMITTED: frozenset({TaskState.WORKING, TaskState.CANCELLED}),
    TaskState.WORKING: frozenset({TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}),
    TaskState.COMPLETED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}


class InvalidTransition(Exception):
    """Raised when a Task is asked to transition along an illegal edge."""


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    kind: Literal["text", "file_reference", "structured"]
    mime_type: str
    content: str | dict[str, Any]
    produced_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Task:
    def __init__(
        self,
        method: str,
        params: dict[str, Any] | None,
        peer_identity: str,
    ) -> None:
        now = datetime.now(UTC)
        self.id: uuid.UUID = uuid.uuid4()
        self.method: str = method
        self.params: dict[str, Any] | None = params
        self.peer_identity: str = peer_identity
        self.state: TaskState = TaskState.SUBMITTED
        self.created_at: datetime = now
        self.last_state_change_at: datetime = now
        self.artifacts: list[Artifact] = []
        self.event_queue: asyncio.Queue[Any] = asyncio.Queue()
        self.process: subprocess.Popen[Any] | asyncio.subprocess.Process | None = None

    def transition(self, new_state: TaskState) -> None:
        old_state = self.state
        allowed = _ALLOWED_TRANSITIONS[old_state]
        if new_state not in allowed:
            raise InvalidTransition(
                f"Illegal transition {old_state.value} -> {new_state.value}"
            )

        if new_state in _TERMINAL_STATES and self.process is not None:
            self.process.terminate()
            self.process = None

        self.state = new_state
        self.last_state_change_at = datetime.now(UTC)

        if new_state in _TERMINAL_STATES:
            self.event_queue.put_nowait(None)

    def add_artifact(self, artifact: Artifact) -> None:
        if self.state is not TaskState.WORKING:
            raise InvalidTransition(
                f"Cannot add artifact in state {self.state.value}; must be working"
            )
        self.artifacts.append(artifact)
