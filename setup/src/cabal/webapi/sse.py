"""SSE event grammar and stream generators for job output and the diagnostics feed.

Job streams carry two frame kinds sharing one ring buffer and sequence space: lossy
`output` text (`Job.append_line`) and typed, replayable events such as `run.progress` /
`cell.complete` / `run.state` (`Job.append_event`, `JobHandle.emit_event`) -- see
`specs/021-codegen-eval-modules/contracts/run-events.md`. Job *kind* does not change
which frame names get emitted; any job can carry either kind, so the same grammar serves
every job kind, `codegen.run` and `evals.matrix` included.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

from cabal.redaction import redact_value
from cabal.webapi.jobs import Job

HEARTBEAT_INTERVAL_S = 10.0
POLL_INTERVAL_S = 0.02
# Job streams are served in bounded segments: the response closes after this long
# even while the job is still running, and the client reconnects with Last-Event-ID
# for a seamless (replay/gap-guarded) continuation. Heartbeats keep the connection
# alive within a segment, so this only bounds how long one response object lives;
# tests override it to keep buffering consumers such as TestClient finite.
JOB_STREAM_SEGMENT_MAX_S = 30.0

SSE_MEDIA_TYPE = "text/event-stream"


def format_event(event: str, data: dict, *, event_id: int | None = None) -> str:
    """Render one SSE frame; every data payload is JSON with pre-redacted strings."""
    payload = json.dumps(redact_value(data))
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {payload}")
    return "\n".join(lines) + "\n\n"


def wants_event_stream(accept_header: str) -> bool:
    return SSE_MEDIA_TYPE in accept_header.lower()


def parse_last_event_id(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


async def job_event_stream(
    job: Job, last_event_id: int | None, *, segment_max_s: float | None = None
) -> AsyncIterator[str]:
    """Replay from the ring buffer (gap event on eviction), then follow live.

    Closes on terminal state, or at the segment deadline while the job still runs —
    the trailing non-terminal state event tells the client to reconnect for more.
    """
    last_seq = last_event_id if last_event_id is not None else -1
    last_emit = time.monotonic()
    # Resolved per call, not as a def-time default, so tests can override the
    # module constant.
    segment = JOB_STREAM_SEGMENT_MAX_S if segment_max_s is None else segment_max_s
    deadline = last_emit + segment
    if not job.is_terminal():
        yield format_event("state", {"state": job.state, "exit_detail": job.exit_detail})
    while True:
        emitted, last_seq = _drain(job, last_seq)
        for frame in emitted:
            last_emit = time.monotonic()
            yield frame
        if job.is_terminal():
            emitted, last_seq = _drain(job, last_seq)
            for frame in emitted:
                yield frame
            yield format_event("state", {"state": job.state, "exit_detail": job.exit_detail})
            return
        if time.monotonic() >= deadline:
            yield format_event("state", {"state": job.state, "exit_detail": job.exit_detail})
            return
        if time.monotonic() - last_emit >= HEARTBEAT_INTERVAL_S:
            last_emit = time.monotonic()
            yield format_event("heartbeat", {"at": last_emit})
        await asyncio.sleep(POLL_INTERVAL_S)


async def terminal_record_stream(record: dict) -> AsyncIterator[str]:
    """Stream for a persisted terminal job: emit the current state immediately, then close."""
    yield format_event("state", {"state": record["state"], "exit_detail": record.get("exit_detail")})


async def diagnostics_event_stream(recorder, last_event_id: int | None) -> AsyncIterator[str]:
    """Live diagnostics feed: replay the in-memory feed, then follow with heartbeats."""
    last_id = last_event_id if last_event_id is not None else 0
    last_emit = time.monotonic()
    while True:
        for event in recorder.feed_after(last_id):
            last_id = event["id"]
            last_emit = time.monotonic()
            yield format_event("diagnostic", event, event_id=event["id"])
        if time.monotonic() - last_emit >= HEARTBEAT_INTERVAL_S:
            last_emit = time.monotonic()
            yield format_event("heartbeat", {"at": last_emit})
        await asyncio.sleep(POLL_INTERVAL_S)


def _drain(job: Job, last_seq: int) -> tuple[list[str], int]:
    """Render buffered frames since last_seq: output lines and structured events
    (`run.progress`, `cell.complete`, ...) share one sequence space (jobs.py T012), so a
    reconnecting client's single Last-Event-ID resumes both, and a gap covers whichever
    kind of frame was evicted.
    """
    job_frames, dropped = job.frames_after(last_seq)
    frames: list[str] = []
    if dropped:
        frames.append(format_event("gap", {"dropped": dropped}))
    for seq, event, data in job_frames:
        payload = {**data, "seq": seq} if event == "output" else data
        frames.append(format_event(event, payload, event_id=seq))
        last_seq = seq
    return frames, last_seq
