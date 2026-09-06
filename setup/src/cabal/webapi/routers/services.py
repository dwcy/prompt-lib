"""Local agent service endpoints and log streams."""

from __future__ import annotations

import asyncio
import hashlib
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from cabal import service_supervisor
from cabal.webapi import security, sse
from cabal.webapi.docker_apps_service import docker_apps_payload
from cabal.webapi.envelope import envelope_response
from cabal.webapi.running_apps_service import running_apps_payload
from cabal.webapi.services_service import (
    service_log_path,
    service_log_snapshot,
    service_payload,
    services_digest,
    services_payload,
)

_SERVICE_LOG_RING_SIZE = 2_000


@dataclass
class _LogState:
    path: Path
    size: int = 0
    digest: bytes = field(default_factory=lambda: hashlib.sha256(b"").digest())
    line_count: int = 0
    next_seq: int = 0
    events: deque[tuple[int, str]] = field(
        default_factory=lambda: deque(maxlen=_SERVICE_LOG_RING_SIZE)
    )


_LOG_STATES: dict[str, _LogState] = {}
_LOG_STATES_LOCK = threading.Lock()

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


@router.get("/api/services")
def list_services():
    return envelope_response(
        data=services_payload(),
        source="services",
        precondition_digest=services_digest(),
    )


@router.get("/api/services/running-apps")
def list_running_apps():
    return envelope_response(data=running_apps_payload(), source="services")


@router.get("/api/services/docker-apps")
def list_docker_apps():
    return envelope_response(data=docker_apps_payload(), source="services")


@router.get("/api/services/{key}")
def get_service(key: str):
    return envelope_response(
        data=service_payload(key),
        source="services",
        precondition_digest=services_digest(key),
    )


@router.get("/api/services/{key}/dashboard")
def service_dashboard(key: str):
    argv, message = service_supervisor.open_dashboard(key)
    return envelope_response(
        data={"key": key, "argv": argv, "message": message, "available": argv is not None},
        source="services",
    )


@router.get("/api/services/{key}/logs")
def service_logs(key: str, tail: int = 120):
    return envelope_response(data=service_log_snapshot(key, tail_lines=tail), source="services")


@router.get("/api/services/{key}/logs/stream")
def service_logs_stream(request: Request, key: str):
    if not sse.wants_event_stream(request.headers.get("accept", "")):
        return envelope_response(data=service_log_snapshot(key), source="services")
    # Validate the key before starting the response so unknown keys are ordinary 404 envelopes.
    service_log_path(key)
    last_event_id = sse.parse_last_event_id(request.headers.get("last-event-id"))
    return StreamingResponse(_service_log_stream(key, last_event_id), media_type=sse.SSE_MEDIA_TYPE)


async def _service_log_stream(key: str, last_event_id: int | None):
    last_seq = last_event_id if last_event_id is not None else -1
    emitted, last_seq = _drain_log(key, last_seq)
    for frame in emitted:
        yield frame
    if not emitted:
        yield sse.format_event("state", {"state": "open", "exit_detail": None})

    deadline = asyncio.get_event_loop().time() + 1.0
    while asyncio.get_event_loop().time() < deadline:
        emitted, last_seq = _drain_log(key, last_seq)
        for frame in emitted:
            yield frame
        await asyncio.sleep(0.1)
    yield sse.format_event("state", {"state": "open", "exit_detail": None})


def _drain_log(key: str, last_seq: int) -> tuple[list[str], int]:
    """Replay a monotonic, restart-aware ring for one captured service log."""
    path = service_log_path(key)
    with _LOG_STATES_LOCK:
        state = _LOG_STATES.get(key)
        if state is None or state.path != path:
            state = _LogState(path=path)
            _LOG_STATES[key] = state
        _refresh_log_state(state)
        events = list(state.events)

    frames: list[str] = []
    if events:
        earliest, latest = events[0][0], events[-1][0]
        if last_seq > latest:
            frames.append(sse.format_event("gap", {"dropped": 0, "reason": "sequence_reset"}))
            last_seq = earliest - 1
        elif last_seq < earliest - 1:
            frames.append(sse.format_event("gap", {"dropped": earliest - last_seq - 1}))
            last_seq = earliest - 1
    for seq, line in events:
        if seq <= last_seq:
            continue
        frames.append(sse.format_event("output", {"line": line, "seq": seq}, event_id=seq))
        last_seq = seq
    return frames, last_seq


def _refresh_log_state(state: _LogState) -> None:
    try:
        content = state.path.read_bytes()
    except FileNotFoundError:
        content = b""
    prefix_unchanged = len(content) >= state.size and hashlib.sha256(content[: state.size]).digest() == state.digest
    lines = content.decode("utf-8", errors="replace").splitlines()
    if not prefix_unchanged:
        state.line_count = 0
    for line in lines[state.line_count :]:
        state.events.append((state.next_seq, line))
        state.next_seq += 1
    state.size = len(content)
    state.digest = hashlib.sha256(content).digest()
    state.line_count = len(lines)
