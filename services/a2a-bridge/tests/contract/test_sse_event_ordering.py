"""Contract tests for the SSE event helpers (T018).

These tests pin the event framing and ordering rules in
``contracts/sse-events.md``: ``task.state`` / ``task.artifact`` /
``task.progress`` are the only event names; every formatted frame ends with
exactly one blank line; the first ``task.state`` of a stream is always
``submitted``; the only legal next state from ``submitted`` is ``working``
or the early-cancel shortcut ``cancelled``; after a terminal state no
further events may be emitted on the same task's stream.

Per Constitution Principle III, this file lands BEFORE its implementation
(T019). Until then every test is expected to fail with ImportError on
``a2a_bridge.protocol.sse``.
"""

from __future__ import annotations

import json

import pytest


def _import_sse():
    from a2a_bridge.protocol import sse

    return sse


def _split_event_frame(frame: str) -> tuple[str, dict]:
    assert frame.endswith("\n\n"), f"frame must end with one blank line, got {frame!r}"
    lines = frame.rstrip("\n").splitlines()
    event_line = next(line for line in lines if line.startswith("event: "))
    data_line = next(line for line in lines if line.startswith("data: "))
    event_name = event_line[len("event: ") :]
    payload = json.loads(data_line[len("data: ") :])
    return event_name, payload


# ---------------------------------------------------------------------------
# format_event — task.state
# ---------------------------------------------------------------------------


class TestFormatTaskStateEvent:
    def test_submitted_state_event_uses_task_state_event_name(self):
        sse = _import_sse()

        frame = sse.format_event(
            sse.TaskStateEvent(task_id="t1", state="submitted", ts="2026-05-10T12:00:00Z")
        )

        event_name, _ = _split_event_frame(frame)
        assert event_name == "task.state"

    def test_submitted_state_event_payload_round_trips(self):
        sse = _import_sse()

        frame = sse.format_event(
            sse.TaskStateEvent(task_id="t1", state="submitted", ts="2026-05-10T12:00:00Z")
        )

        _, payload = _split_event_frame(frame)
        assert payload == {
            "task_id": "t1",
            "state": "submitted",
            "ts": "2026-05-10T12:00:00Z",
        }

    def test_failed_state_event_includes_optional_failure_fields(self):
        sse = _import_sse()

        frame = sse.format_event(
            sse.TaskStateEvent(
                task_id="t1",
                state="failed",
                ts="2026-05-10T12:00:01Z",
                reason="cli_nonzero_exit",
                exit_code=2,
                stderr_tail="boom",
            )
        )

        _, payload = _split_event_frame(frame)
        assert payload["reason"] == "cli_nonzero_exit"
        assert payload["exit_code"] == 2
        assert payload["stderr_tail"] == "boom"

    def test_state_event_omits_unset_optional_fields(self):
        sse = _import_sse()

        frame = sse.format_event(
            sse.TaskStateEvent(task_id="t1", state="working", ts="2026-05-10T12:00:00Z")
        )

        _, payload = _split_event_frame(frame)
        assert "reason" not in payload
        assert "exit_code" not in payload
        assert "stderr_tail" not in payload


# ---------------------------------------------------------------------------
# format_event — task.artifact
# ---------------------------------------------------------------------------


class TestFormatTaskArtifactEvent:
    def test_artifact_event_uses_task_artifact_name(self):
        sse = _import_sse()

        frame = sse.format_event(
            sse.TaskArtifactEvent(
                task_id="t1",
                artifact={
                    "id": "a1",
                    "kind": "text",
                    "mime_type": "text/plain",
                    "content": "pong",
                    "produced_at": "2026-05-10T12:00:01Z",
                },
            )
        )

        event_name, _ = _split_event_frame(frame)
        assert event_name == "task.artifact"

    def test_artifact_event_carries_full_artifact_payload(self):
        sse = _import_sse()

        artifact = {
            "id": "a1",
            "kind": "text",
            "mime_type": "text/plain",
            "content": "pong",
            "produced_at": "2026-05-10T12:00:01Z",
        }
        frame = sse.format_event(sse.TaskArtifactEvent(task_id="t1", artifact=artifact))

        _, payload = _split_event_frame(frame)
        assert payload == {"task_id": "t1", "artifact": artifact}


# ---------------------------------------------------------------------------
# format_event — task.progress
# ---------------------------------------------------------------------------


class TestFormatTaskProgressEvent:
    def test_progress_event_uses_task_progress_name(self):
        sse = _import_sse()

        frame = sse.format_event(
            sse.TaskProgressEvent(
                task_id="t1", message="working...", ts="2026-05-10T12:00:00Z"
            )
        )

        event_name, _ = _split_event_frame(frame)
        assert event_name == "task.progress"

    def test_progress_event_payload_round_trips(self):
        sse = _import_sse()

        frame = sse.format_event(
            sse.TaskProgressEvent(
                task_id="t1", message="working...", ts="2026-05-10T12:00:00Z"
            )
        )

        _, payload = _split_event_frame(frame)
        assert payload == {
            "task_id": "t1",
            "message": "working...",
            "ts": "2026-05-10T12:00:00Z",
        }


# ---------------------------------------------------------------------------
# SSE framing — every formatted event ends with exactly one blank line
# ---------------------------------------------------------------------------


class TestEventFramingTerminator:
    def test_state_frame_ends_with_one_blank_line(self):
        sse = _import_sse()

        frame = sse.format_event(
            sse.TaskStateEvent(task_id="t1", state="submitted", ts="2026-05-10T12:00:00Z")
        )

        assert frame.endswith("\n\n")
        assert not frame.endswith("\n\n\n")

    def test_artifact_frame_ends_with_one_blank_line(self):
        sse = _import_sse()

        frame = sse.format_event(
            sse.TaskArtifactEvent(
                task_id="t1",
                artifact={
                    "id": "a1",
                    "kind": "text",
                    "mime_type": "text/plain",
                    "content": "pong",
                    "produced_at": "2026-05-10T12:00:01Z",
                },
            )
        )

        assert frame.endswith("\n\n")
        assert not frame.endswith("\n\n\n")

    def test_progress_frame_ends_with_one_blank_line(self):
        sse = _import_sse()

        frame = sse.format_event(
            sse.TaskProgressEvent(
                task_id="t1", message="step", ts="2026-05-10T12:00:00Z"
            )
        )

        assert frame.endswith("\n\n")
        assert not frame.endswith("\n\n\n")


# ---------------------------------------------------------------------------
# OrderingEnforcer — happy path
# ---------------------------------------------------------------------------


class TestOrderingEnforcerHappyPath:
    def test_first_event_must_be_submitted(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")

        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))

    def test_submitted_then_working_is_allowed(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")

        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="working", ts="t"))

    def test_working_then_progress_then_artifact_then_completed_is_allowed(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")

        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="working", ts="t"))
        enforcer.check(sse.TaskProgressEvent(task_id="t1", message="hi", ts="t"))
        enforcer.check(
            sse.TaskArtifactEvent(
                task_id="t1",
                artifact={
                    "id": "a1",
                    "kind": "text",
                    "mime_type": "text/plain",
                    "content": "pong",
                    "produced_at": "t",
                },
            )
        )
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="completed", ts="t"))

    def test_multiple_progress_events_after_working_are_allowed(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")

        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="working", ts="t"))
        for _ in range(3):
            enforcer.check(sse.TaskProgressEvent(task_id="t1", message="...", ts="t"))

    def test_multiple_artifact_events_after_working_are_allowed(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")

        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="working", ts="t"))
        for idx in range(2):
            enforcer.check(
                sse.TaskArtifactEvent(
                    task_id="t1",
                    artifact={
                        "id": f"a{idx}",
                        "kind": "text",
                        "mime_type": "text/plain",
                        "content": f"chunk-{idx}",
                        "produced_at": "t",
                    },
                )
            )

    def test_submitted_then_cancelled_is_allowed_for_early_cancel(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")

        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="cancelled", ts="t"))


# ---------------------------------------------------------------------------
# OrderingEnforcer — violations
# ---------------------------------------------------------------------------


class TestOrderingEnforcerRejectsViolations:
    def test_event_for_other_task_id_raises_ordering_violation(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")

        with pytest.raises(sse.OrderingViolation):
            enforcer.check(sse.TaskStateEvent(task_id="other", state="submitted", ts="t"))

    def test_first_event_other_than_submitted_raises_ordering_violation(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")

        with pytest.raises(sse.OrderingViolation):
            enforcer.check(sse.TaskStateEvent(task_id="t1", state="working", ts="t"))

    def test_submitted_to_completed_directly_raises_ordering_violation(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))

        with pytest.raises(sse.OrderingViolation):
            enforcer.check(sse.TaskStateEvent(task_id="t1", state="completed", ts="t"))

    def test_submitted_to_failed_directly_raises_ordering_violation(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))

        with pytest.raises(sse.OrderingViolation):
            enforcer.check(sse.TaskStateEvent(task_id="t1", state="failed", ts="t"))

    def test_two_consecutive_submitted_events_raise_ordering_violation(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))

        with pytest.raises(sse.OrderingViolation):
            enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))

    @pytest.mark.parametrize("terminal", ["completed", "failed", "cancelled"])
    def test_no_event_allowed_after_terminal_state(self, terminal: str):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="working", ts="t"))
        enforcer.check(sse.TaskStateEvent(task_id="t1", state=terminal, ts="t"))

        with pytest.raises(sse.OrderingViolation):
            enforcer.check(sse.TaskProgressEvent(task_id="t1", message="late", ts="t"))

    @pytest.mark.parametrize("terminal", ["completed", "failed", "cancelled"])
    def test_no_artifact_allowed_after_terminal_state(self, terminal: str):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="working", ts="t"))
        enforcer.check(sse.TaskStateEvent(task_id="t1", state=terminal, ts="t"))

        with pytest.raises(sse.OrderingViolation):
            enforcer.check(
                sse.TaskArtifactEvent(
                    task_id="t1",
                    artifact={
                        "id": "a1",
                        "kind": "text",
                        "mime_type": "text/plain",
                        "content": "late",
                        "produced_at": "t",
                    },
                )
            )

    def test_no_state_event_allowed_after_terminal_state(self):
        sse = _import_sse()

        enforcer = sse.OrderingEnforcer(task_id="t1")
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="submitted", ts="t"))
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="working", ts="t"))
        enforcer.check(sse.TaskStateEvent(task_id="t1", state="completed", ts="t"))

        with pytest.raises(sse.OrderingViolation):
            enforcer.check(sse.TaskStateEvent(task_id="t1", state="working", ts="t"))
