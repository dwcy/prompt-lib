"""Contract tests for specs/021-codegen-eval-modules/contracts/run-events.md.

The SSE run-event grammar is deliberately liveness-only (research.md R4): the ring
buffer holds only `DEFAULT_RING_BUFFER_SIZE` frames, an eval matrix emits far more, and
each response segment closes after `JOB_STREAM_SEGMENT_MAX_S`. A client that reconnects
with Last-Event-ID must therefore be able to rebuild correct state from typed
`run.progress` / `cell.complete` / `run.state` events plus the artifact tree -- never
from having seen every frame (contract's central property).

`run_supervisor.py` (T008-T014, Phase 2) is still a stub, and today's shared job/SSE
grammar (`cabal.webapi.jobs.Job`, `cabal.webapi.sse.job_event_stream`) only knows four
event names: output|state|heartbeat|gap. It has no channel yet for a typed
`run.progress`, `cell.complete`, or `run.gate` event (T012). Job *kind* is pure metadata
in that grammar today -- it does not change what gets emitted -- so reusing the
existing `test.job_emitter` fixture action (rather than inventing a codegen/evals-only
one) exercises exactly the same kind-agnostic gap that a real `codegen.run` or
`evals.matrix` job would run through once launched.
"""

from __future__ import annotations

import json
import typing

from .webapi_fixtures import (
    app_factory,
    auth_headers,
    build_client,
    register_fixture_actions,
)

__all__ = ["app_factory"]


def _create_job(client, **params) -> str:
    prepared = client.post(
        "/api/actions/test.job_emitter/prepare",
        json=params,
        headers=auth_headers(),
    )
    assert prepared.status_code == 200, prepared.text
    ticket_id = prepared.json()["data"]["ticket_id"]

    executed = client.post(
        "/api/actions/test.job_emitter/execute",
        json={"ticket_id": ticket_id},
        headers=auth_headers(),
    )
    assert executed.status_code == 202, executed.text
    return executed.json()["data"]["job_id"]


def _cancel_job(client, job_id: str) -> None:
    prepared = client.post(
        "/api/actions/jobs.cancel/prepare",
        json={"job_id": job_id},
        headers=auth_headers(),
    )
    assert prepared.status_code == 200, prepared.text
    executed = client.post(
        "/api/actions/jobs.cancel/execute",
        json={"ticket_id": prepared.json()["data"]["ticket_id"]},
        headers=auth_headers(),
    )
    assert executed.status_code in {200, 202}, executed.text


def _read_events(stream_response) -> list[dict]:
    events: list[dict] = []
    current_event = "message"
    for raw_line in stream_response.iter_lines():
        line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8")
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            payload = json.loads(line.split(":", 1)[1].strip())
            events.append({"event": current_event, "data": payload})
    return events


def test_client_disconnected_past_ring_buffer_reconnects_to_typed_absolute_progress(
    app_factory,
) -> None:
    """Guards research.md R4, the contract's central property: a client absent longer
    than the ring buffer's depth must still land on correct state from typed events,
    with the gap it missed made explicit -- never inferred by scraping the lossy output
    tail, and never silent (a silent gap would let the client believe it has a complete
    picture when it does not)."""
    from cabal.webapi.jobs import DEFAULT_RING_BUFFER_SIZE

    app, client = build_client(app_factory)
    register_fixture_actions(app)

    total_lines = DEFAULT_RING_BUFFER_SIZE + 100
    job_id = _create_job(client, lines=total_lines, delay_ms=0, ring_buffer_size=DEFAULT_RING_BUFFER_SIZE)

    # Drive the job to completion via one connection (matching the existing
    # last-event-id contract test's pattern) -- its frames are discarded here because
    # this test is about a *second*, later client that never saw any of them.
    with client.stream("GET", f"/api/jobs/{job_id}/stream", headers=auth_headers()) as first_pass:
        _read_events(first_pass)

    with client.stream(
        "GET",
        f"/api/jobs/{job_id}/stream",
        headers={**auth_headers(), "Last-Event-ID": "0"},
    ) as replay:
        events = _read_events(replay)

    gap_events = [e for e in events if e["event"] == "gap"]
    assert gap_events and gap_events[0]["data"]["dropped"] > 0, (
        "a client absent past the ring buffer's depth must see an explicit gap, not "
        "silent continuity -- contract: 'a silent gap is a defect'"
    )

    progress_events = [e for e in events if e["event"] in {"run.progress", "cell.complete"}]
    assert progress_events, (
        "contract requires run.progress/cell.complete as typed SSE events so a client "
        "who missed frames can rebuild absolute state from the last surviving one alone; "
        "today's grammar (cabal.webapi.sse.job_event_stream) only ever emits "
        "output|state|heartbeat|gap, so a reconnecting client has nothing to rebuild "
        "state from (T012 not yet implemented)"
    )
    last_progress = progress_events[-1]["data"]
    completed = last_progress.get("completed", last_progress.get("stage_index"))
    total = last_progress.get("total", last_progress.get("stage_count"))
    assert completed == total, "the last surviving frame must show the run finished, not a delta count"


def test_progress_and_cell_complete_events_carry_absolute_position_not_deltas(app_factory) -> None:
    """A client joining mid-run must read where things stand from a single frame; a
    design that made these events carry deltas would force replaying every prior frame
    to reconstruct a position -- exactly the thing the 200-frame ring buffer structurally
    cannot guarantee (contract for `run.progress` and `cell.complete`)."""
    app, client = build_client(app_factory)
    register_fixture_actions(app)
    job_id = _create_job(client, lines=5, delay_ms=20)

    with client.stream("GET", f"/api/jobs/{job_id}/stream", headers=auth_headers()) as stream:
        events = _read_events(stream)

    progress_events = [e for e in events if e["event"] in {"run.progress", "cell.complete"}]
    assert progress_events, (
        "no typed run.progress/cell.complete events were emitted; the current grammar "
        "(cabal.webapi.sse) has no structured-event channel yet, only output text (T012)"
    )
    positions = [
        (
            e["data"].get("completed", e["data"].get("stage_index")),
            e["data"].get("total", e["data"].get("stage_count")),
        )
        for e in progress_events
    ]
    totals = [total for _, total in positions]
    completed_values = [completed for completed, _ in positions]
    assert all(total == totals[0] for total in totals), "total/stage_count must stay fixed across one run"
    assert completed_values == sorted(completed_values), (
        "position must be absolute and non-decreasing across frames, not a per-frame delta"
    )


def test_pending_gate_is_discoverable_from_read_surface_without_ever_streaming(app_factory) -> None:
    """`run.gate` is a notification, not the gate itself (research.md R3): the durable
    approval gate is the subsystem's on-disk pending intent, so a client that never
    connects to any SSE stream at all must still be able to find it via
    `GET /api/codegen/pending`. This test never opens `/api/jobs/*/stream`, proving the
    read surface alone is sufficient -- the deeper shape of the gate payload itself is
    `contracts/codegen-api.md`'s concern (test_codegen_api.py, T016), not this file's."""
    app, client = build_client(app_factory)
    register_fixture_actions(app)

    pending = client.get("/api/codegen/pending", headers=auth_headers())

    assert pending.status_code == 200, (
        f"the pending gate must be readable without ever touching the SSE stream, got "
        f"{pending.status_code}: {pending.text}"
    )
    body = pending.json()["data"]
    assert body is None or {"token", "files"} <= body.keys()


def test_interrupted_state_comes_only_from_read_time_reconciliation_never_the_run(
    app_factory, tmp_path
) -> None:
    """research.md R2: a process that died cannot report its own death, so `interrupted`
    must be a value `reconcile_state()` computes at read time from process liveness plus
    the artifact tree -- never a state the run itself, or `JobManager.finish`, writes
    into the `jobs` table (data-model B1, T009/T010). Proven against the exact stranded-
    row scenario research.md R1 describes: a job the JobManager still calls "running"."""
    from cabal.webapi import run_supervisor

    allowed_states = set(typing.get_args(run_supervisor.RunState))
    assert allowed_states == {"running", "succeeded", "failed", "cancelled", "interrupted"}

    app, client = build_client(app_factory)
    register_fixture_actions(app)
    job_id = _create_job(client, lines=20, delay_ms=100)
    record = client.get(f"/api/jobs/{job_id}", headers=auth_headers()).json()["data"]
    assert record["state"] == "running"

    incomplete_artifacts = tmp_path / "evals-results" / "stranded-run"
    incomplete_artifacts.mkdir(parents=True)
    (incomplete_artifacts / "manifest.json").write_text("{}", encoding="utf-8")

    run = run_supervisor.SupervisedRun(
        job_id=job_id,
        kind="evals.matrix",
        run_id="stranded-run",
        pid=2**30,  # never a live pid on this machine
        artifact_root=str(incomplete_artifacts),
        exclusive_resource="evals",
    )

    reconciled = run_supervisor.reconcile_state(run)

    assert reconciled == "interrupted", (
        "a dead pid plus an incomplete artifact tree must reconcile to 'interrupted' "
        "at read time (T009)"
    )
    stale_record = client.get(f"/api/jobs/{job_id}", headers=auth_headers()).json()["data"]
    assert stale_record["state"] == "running", (
        "the jobs table's own state column must be untouched by reconciliation -- "
        "'interrupted' is a presentation value layered on top, never persisted (T010)"
    )

    _cancel_job(client, job_id)


def test_reconnecting_client_need_not_parse_output_to_learn_final_progress(app_factory) -> None:
    """`output.append` is explicitly lossy (contract): nothing a client needs may live
    only there. This asserts the converse holds -- final progress must be recoverable
    from non-output events alone, i.e. a structured event, never by scraping text."""
    app, client = build_client(app_factory)
    register_fixture_actions(app)
    total_lines = 12
    job_id = _create_job(client, lines=total_lines, delay_ms=5)

    with client.stream("GET", f"/api/jobs/{job_id}/stream", headers=auth_headers()) as stream:
        events = _read_events(stream)

    non_output_events = [e for e in events if e["event"] != "output"]
    progress_or_cell = [e for e in non_output_events if e["event"] in {"run.progress", "cell.complete"}]
    assert progress_or_cell, (
        "a client that never parses output.append text has no evidence of progress at "
        "all under the current grammar -- run.progress/cell.complete must exist as "
        "their own typed events (T012), independent of the lossy output tail"
    )
    final = progress_or_cell[-1]["data"]
    assert final.get("completed", final.get("stage_index")) == total_lines


def test_no_cost_update_event_is_ever_emitted(app_factory) -> None:
    """Contract's 'What is deliberately absent': cost is read from the run record after
    the fact, never streamed, so it can never diverge from the CLI's own figures
    (SC-010). A forward-looking regression guard, not a T012 gap -- nothing in today's
    grammar emits any custom event name either, so this currently passes vacuously."""
    app, client = build_client(app_factory)
    register_fixture_actions(app)
    job_id = _create_job(client, lines=10, delay_ms=1)

    with client.stream("GET", f"/api/jobs/{job_id}/stream", headers=auth_headers()) as stream:
        events = _read_events(stream)

    assert all(e["event"] != "cost.update" for e in events)
