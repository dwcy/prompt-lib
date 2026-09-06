"""Job lifecycle: state machine, output ring buffer, exclusive resources, terminal persistence."""

from __future__ import annotations

import contextlib
import threading
import uuid
from collections import deque
from collections.abc import Callable
from typing import Literal

from cabal.redaction import redact_text
from cabal.webapi.envelope import utc_now_iso
from cabal.webapi.storage import Storage

TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})
DEFAULT_RING_BUFFER_SIZE = 200
OUTPUT_TAIL_LIMIT = 200

FinishState = Literal["succeeded", "failed", "cancelled"]


class JobConflict(Exception):
    """Raised by JobManager.create when the exclusive resource is already held."""

    def __init__(self, blocking_job_id: str) -> None:
        super().__init__(f"resource held by job {blocking_job_id}")
        self.blocking_job_id = blocking_job_id


class Job:
    """One observable long-running operation with a seq-numbered output ring buffer."""

    def __init__(
        self,
        job_id: str,
        kind: str,
        *,
        ticket_id: str | None,
        exclusive_resource: str | None,
        ring_buffer_size: int,
    ) -> None:
        self.job_id = job_id
        self.kind = kind
        self.ticket_id = ticket_id
        self.exclusive_resource = exclusive_resource
        self.state = "queued"
        self.exit_detail: str | None = None
        self.created_at = utc_now_iso()
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self._lock = threading.Lock()
        # One ring buffer, one sequence space, for both output lines and structured
        # events (021-codegen-eval-modules T012 / contracts/run-events.md): a client's
        # single Last-Event-ID must resume both channels together, and the contract's
        # gap/eviction guarantee has to hold regardless of which kind of frame filled
        # the buffer. Each entry is (seq, sse_event_name, payload).
        self._frames: deque[tuple[int, str, dict]] = deque(maxlen=max(1, ring_buffer_size))
        self._tail: deque[str] = deque(maxlen=OUTPUT_TAIL_LIMIT)
        self._next_seq = 0
        self._cancel_event = threading.Event()

    def append_line(self, text: str) -> None:
        redacted = redact_text(text)
        with self._lock:
            self._frames.append((self._next_seq, "output", {"line": redacted}))
            self._tail.append(redacted)
            self._next_seq += 1

    def append_event(self, event: str, data: dict) -> None:
        """Emit a structured, replayable event (`run.progress`, `cell.complete`, ...)
        sharing the output ring buffer's sequence space and eviction/gap semantics, so a
        reconnecting client's Last-Event-ID covers both kinds of frame (contracts/run-events.md).
        Redaction happens at serialization (`sse.format_event`), same as output lines.
        """
        with self._lock:
            self._frames.append((self._next_seq, event, dict(data)))
            self._next_seq += 1

    def frames_after(self, last_seq: int) -> tuple[list[tuple[int, str, dict]], int]:
        """Return buffered frames newer than last_seq plus the count evicted before them."""
        with self._lock:
            available = [(seq, event, data) for seq, event, data in self._frames if seq > last_seq]
            dropped = 0
            if available and available[0][0] > last_seq + 1:
                dropped = available[0][0] - last_seq - 1
            return available, dropped

    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    def set_ticket_id(self, ticket_id: str) -> None:
        with self._lock:
            self.ticket_id = ticket_id

    def record(self) -> dict:
        with self._lock:
            return {
                "job_id": self.job_id,
                "kind": self.kind,
                "ticket_id": self.ticket_id,
                "state": self.state,
                "output_tail": list(self._tail),
                "exit_detail": self.exit_detail,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
            }


class JobHandle:
    """The runner-facing seam: emit output, observe cancellation, declare the outcome."""

    def __init__(self, job: Job, manager: JobManager) -> None:
        self._job = job
        self._manager = manager

    @property
    def job_id(self) -> str:
        """The real `Job.job_id`, so a runner can persist a supervised-run handle
        (021-codegen-eval-modules T018/T019) keyed by the same id the client's 202
        response and `/api/jobs/{job_id}` already use -- without a race against
        `JobManager.create` starting the runner thread before its return value is
        assigned on the caller's side."""
        return self._job.job_id

    def emit_line(self, text: str) -> None:
        self._job.append_line(text)

    def emit_event(self, event: str, data: dict) -> None:
        self._job.append_event(event, data)

    def is_cancelled(self) -> bool:
        return self._job.is_cancelled()

    def finish(self, state: FinishState, exit_detail: str | None = None) -> None:
        self._manager.finish(self._job, state, exit_detail=exit_detail)


class JobManager:
    """Owns job creation, cancellation, exclusive resources, and terminal persistence."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._resources: dict[str, str] = {}
        self._terminal_callbacks: dict[str, list[Callable[[dict], None]]] = {}

    def create(
        self,
        kind: str,
        *,
        runner: Callable[[JobHandle], None],
        ticket_id: str | None = None,
        exclusive_resource: str | None = None,
        ring_buffer_size: int = DEFAULT_RING_BUFFER_SIZE,
    ) -> Job:
        job = Job(
            str(uuid.uuid4()),
            kind,
            ticket_id=ticket_id,
            exclusive_resource=exclusive_resource,
            ring_buffer_size=ring_buffer_size,
        )
        with self._lock:
            if exclusive_resource is not None:
                holder = self._resources.get(exclusive_resource)
                if holder is not None:
                    raise JobConflict(holder)
                self._resources[exclusive_resource] = job.job_id
            self._jobs[job.job_id] = job
        thread = threading.Thread(target=self._run, args=(job, runner), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def get_record(self, job_id: str) -> dict | None:
        """Live record when in memory, otherwise the persisted terminal record."""
        job = self.get(job_id)
        if job is not None:
            return job.record()
        return self._storage.load_job(job_id)

    def list_records(self) -> list[dict]:
        records = {record["job_id"]: record for record in self._storage.list_jobs()}
        for job in self.list():
            records[job.job_id] = job.record()
        return sorted(records.values(), key=lambda record: record["created_at"])

    def cancel(self, job_id: str) -> bool:
        """Idempotent: queued/running -> cancelled; terminal jobs stay untouched."""
        job = self.get(job_id)
        if job is None:
            return self._storage.load_job(job_id) is not None
        job.request_cancel()
        if not job.is_terminal():
            self.finish(job, "cancelled")
        return True

    def attach_ticket(self, job_id: str, ticket_id: str) -> None:
        """Link an action-created job to its confirmation ticket without a finish race."""
        job = self.get(job_id)
        if job is None:
            record = self._storage.load_job(job_id)
            if record is None:
                raise KeyError(f"unknown job {job_id}")
            record["ticket_id"] = ticket_id
            self._storage.save_job(record)
            return
        job.set_ticket_id(ticket_id)
        if job.is_terminal():
            self._storage.save_job(job.record())

    def add_terminal_callback(self, job_id: str, callback: Callable[[dict], None]) -> None:
        job = self.get(job_id)
        if job is None:
            return
        fire_now = False
        with self._lock:
            if job.is_terminal():
                fire_now = True
            else:
                self._terminal_callbacks.setdefault(job_id, []).append(callback)
        if fire_now:
            callback(job.record())

    def finish(self, job: Job, state: FinishState, *, exit_detail: str | None = None) -> None:
        with self._lock:
            if job.is_terminal():
                return
            job.state = state
            job.exit_detail = redact_text(exit_detail) if exit_detail else None
            job.finished_at = utc_now_iso()
            callbacks = self._terminal_callbacks.pop(job.job_id, [])
        record = job.record()
        # Suppress persistence errors from late daemon-thread finishes (e.g. the
        # storage file's temp dir disappearing after a test session ends).
        with contextlib.suppress(Exception):
            self._storage.save_job(record)
        for callback in callbacks:
            with contextlib.suppress(Exception):
                callback(record)

    def _release_resource(self, job: Job) -> None:
        """Held until the runner thread actually returns.

        cancel() marks a job terminal while its runner is still executing; releasing
        the resource there would let a second job start alongside the live one.
        """
        if job.exclusive_resource is None:
            return
        with self._lock:
            if self._resources.get(job.exclusive_resource) == job.job_id:
                del self._resources[job.exclusive_resource]

    def _run(self, job: Job, runner: Callable[[JobHandle], None]) -> None:
        try:
            with self._lock:
                if job.is_terminal():
                    return
                job.state = "running"
                job.started_at = utc_now_iso()
            handle = JobHandle(job, self)
            try:
                runner(handle)
            except Exception as exc:
                self.finish(job, "failed", exit_detail=str(exc))
            else:
                self.finish(job, "succeeded")
        finally:
            self._release_resource(job)
