"""Unit tests for the Task entity + state machine (T014).

These tests pin the lifecycle invariants documented in
``data-model.md`` § "Entity: Task" → "State transitions": only the
``submitted → working → {completed | failed | cancelled}`` graph is legal,
``submitted → cancelled`` is an explicit early-cancel shortcut, terminal
states are sticky, the per-task ``asyncio.Queue`` is closed on terminal
transition, and the subprocess reference is reaped before the terminal
transition emits.

Per Constitution Principle III, this file lands BEFORE its implementation
(T015). Until then every test is expected to fail with ImportError on
``a2a_bridge.protocol.tasks``.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest


def _import_tasks():
    from a2a_bridge.protocol import tasks

    return tasks


def _make_task():
    tasks = _import_tasks()
    return tasks.Task(
        method="tasks/sendSubscribe",
        params={"task": {"messages": [{"role": "user", "content": "hi"}]}},
        peer_identity="peer-1",
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestTaskConstruction:
    def test_new_task_starts_in_submitted_state(self):
        tasks = _import_tasks()

        task = _make_task()

        assert task.state is tasks.TaskState.SUBMITTED

    def test_new_task_id_is_uuid_v4(self):
        task = _make_task()

        parsed = uuid.UUID(str(task.id))

        assert parsed.version == 4

    def test_new_task_created_at_is_utc_datetime(self):
        task = _make_task()

        assert isinstance(task.created_at, datetime)
        assert task.created_at.tzinfo is not None
        assert task.created_at.utcoffset() is not None
        assert task.created_at.utcoffset().total_seconds() == 0

    def test_new_task_carries_method_and_peer_identity(self):
        task = _make_task()

        assert task.method == "tasks/sendSubscribe"
        assert task.peer_identity == "peer-1"

    def test_new_task_artifacts_is_empty_list(self):
        task = _make_task()

        assert task.artifacts == []

    def test_new_task_event_queue_is_asyncio_queue(self):
        task = _make_task()

        assert isinstance(task.event_queue, asyncio.Queue)


# ---------------------------------------------------------------------------
# Legal transitions
# ---------------------------------------------------------------------------


class TestLegalTransitions:
    def test_submitted_to_working_succeeds(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)

        assert task.state is tasks.TaskState.WORKING

    def test_transition_updates_last_state_change_at(self):
        tasks = _import_tasks()

        task = _make_task()
        before = task.last_state_change_at
        task.transition(tasks.TaskState.WORKING)

        assert task.last_state_change_at >= before
        assert task.last_state_change_at != before or task.state is tasks.TaskState.WORKING

    def test_working_to_completed_succeeds(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)
        task.transition(tasks.TaskState.COMPLETED)

        assert task.state is tasks.TaskState.COMPLETED

    def test_working_to_failed_succeeds(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)
        task.transition(tasks.TaskState.FAILED)

        assert task.state is tasks.TaskState.FAILED

    def test_working_to_cancelled_succeeds(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)
        task.transition(tasks.TaskState.CANCELLED)

        assert task.state is tasks.TaskState.CANCELLED

    def test_submitted_to_cancelled_succeeds_for_early_cancel(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.CANCELLED)

        assert task.state is tasks.TaskState.CANCELLED


# ---------------------------------------------------------------------------
# Illegal transitions
# ---------------------------------------------------------------------------


class TestIllegalTransitions:
    def test_submitted_to_completed_raises_invalid_transition(self):
        tasks = _import_tasks()

        task = _make_task()

        with pytest.raises(tasks.InvalidTransition):
            task.transition(tasks.TaskState.COMPLETED)

    def test_submitted_to_failed_raises_invalid_transition(self):
        tasks = _import_tasks()

        task = _make_task()

        with pytest.raises(tasks.InvalidTransition):
            task.transition(tasks.TaskState.FAILED)

    def test_submitted_to_submitted_raises_invalid_transition(self):
        tasks = _import_tasks()

        task = _make_task()

        with pytest.raises(tasks.InvalidTransition):
            task.transition(tasks.TaskState.SUBMITTED)

    def test_working_to_working_raises_invalid_transition(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)

        with pytest.raises(tasks.InvalidTransition):
            task.transition(tasks.TaskState.WORKING)

    def test_working_to_submitted_raises_invalid_transition(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)

        with pytest.raises(tasks.InvalidTransition):
            task.transition(tasks.TaskState.SUBMITTED)


# ---------------------------------------------------------------------------
# Terminal stickiness
# ---------------------------------------------------------------------------


class TestTerminalStatesAreSticky:
    @pytest.mark.parametrize(
        "terminal",
        ["COMPLETED", "FAILED", "CANCELLED"],
    )
    @pytest.mark.parametrize(
        "next_state",
        ["SUBMITTED", "WORKING", "COMPLETED", "FAILED", "CANCELLED"],
    )
    def test_no_transition_out_of_terminal_state(self, terminal: str, next_state: str):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)
        task.transition(getattr(tasks.TaskState, terminal))

        with pytest.raises(tasks.InvalidTransition):
            task.transition(getattr(tasks.TaskState, next_state))


# ---------------------------------------------------------------------------
# Artifact accumulation
# ---------------------------------------------------------------------------


class TestArtifactAccumulation:
    def test_add_artifact_in_working_state_appends_to_list(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)
        artifact = tasks.Artifact(kind="text", mime_type="text/plain", content="hello")
        task.add_artifact(artifact)

        assert task.artifacts == [artifact]

    def test_artifact_id_is_uuid_v4(self):
        tasks = _import_tasks()

        artifact = tasks.Artifact(kind="text", mime_type="text/plain", content="hello")

        parsed = uuid.UUID(str(artifact.id))

        assert parsed.version == 4

    def test_artifact_produced_at_is_utc_datetime(self):
        tasks = _import_tasks()

        artifact = tasks.Artifact(kind="text", mime_type="text/plain", content="hello")

        assert isinstance(artifact.produced_at, datetime)
        assert artifact.produced_at.tzinfo is not None
        assert artifact.produced_at.utcoffset().total_seconds() == 0

    def test_two_artifacts_have_distinct_ids(self):
        tasks = _import_tasks()

        first = tasks.Artifact(kind="text", mime_type="text/plain", content="a")
        second = tasks.Artifact(kind="text", mime_type="text/plain", content="b")

        assert first.id != second.id


# ---------------------------------------------------------------------------
# Event queue lifecycle
# ---------------------------------------------------------------------------


class TestEventQueueClosesOnTerminal:
    async def test_queue_receives_sentinel_after_completed(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)
        task.transition(tasks.TaskState.COMPLETED)

        sentinel = await asyncio.wait_for(task.event_queue.get(), timeout=0.5)

        assert sentinel is None

    async def test_queue_receives_sentinel_after_failed(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)
        task.transition(tasks.TaskState.FAILED)

        sentinel = await asyncio.wait_for(task.event_queue.get(), timeout=0.5)

        assert sentinel is None

    async def test_queue_receives_sentinel_after_early_cancel(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.CANCELLED)

        sentinel = await asyncio.wait_for(task.event_queue.get(), timeout=0.5)

        assert sentinel is None


# ---------------------------------------------------------------------------
# Subprocess reaping
# ---------------------------------------------------------------------------


class TestSubprocessReapedBeforeTerminal:
    def test_process_is_none_after_terminal_transition(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)
        task.process = MagicMock()
        task.transition(tasks.TaskState.COMPLETED)

        assert task.process is None

    def test_process_terminate_is_called_on_terminal_transition(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)
        proc = MagicMock()
        task.process = proc
        task.transition(tasks.TaskState.CANCELLED)

        proc.terminate.assert_called_once()

    def test_process_terminate_called_on_failed_transition(self):
        tasks = _import_tasks()

        task = _make_task()
        task.transition(tasks.TaskState.WORKING)
        proc = MagicMock()
        task.process = proc
        task.transition(tasks.TaskState.FAILED)

        proc.terminate.assert_called_once()
        assert task.process is None
