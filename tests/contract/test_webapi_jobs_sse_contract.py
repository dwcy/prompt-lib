"""Contract tests for specs/015-web-ui-overhaul/contracts/jobs-and-streams.contract.md."""

from __future__ import annotations

import json

from .webapi_fixtures import (
    FAKE_SECRET,
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


def test_job_lifecycle_reaches_terminal_state_with_monotonic_seq(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)
    job_id = _create_job(client, lines=5, delay_ms=5)

    with client.stream("GET", f"/api/jobs/{job_id}/stream", headers=auth_headers()) as stream:
        assert stream.status_code == 200
        events = _read_events(stream)

    output_events = [e for e in events if e["event"] == "output"]
    seqs = [e["data"]["seq"] for e in output_events]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)

    state_events = [e for e in events if e["event"] == "state"]
    assert state_events[-1]["data"]["state"] == "succeeded"

    record = client.get(f"/api/jobs/{job_id}", headers=auth_headers())
    assert record.json()["data"]["state"] == "succeeded"


def test_cancel_reflected_on_stream_and_on_job_get(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)
    job_id = _create_job(client, lines=50, delay_ms=50)

    with client.stream("GET", f"/api/jobs/{job_id}/stream", headers=auth_headers()) as stream:
        for raw_line in stream.iter_lines():
            line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8")
            if line.startswith("event:") and line.split(":", 1)[1].strip() == "output":
                cancel_response = client.post(
                    f"/api/jobs/{job_id}/cancel",
                    headers=auth_headers(),
                )
                assert cancel_response.status_code == 200
                break

    record = client.get(f"/api/jobs/{job_id}", headers=auth_headers())
    assert record.json()["data"]["state"] == "cancelled"


def test_last_event_id_replay_without_dupes_and_gap_on_eviction(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)
    job_id = _create_job(client, lines=10, delay_ms=2, ring_buffer_size=3)

    with client.stream("GET", f"/api/jobs/{job_id}/stream", headers=auth_headers()) as first_pass:
        _read_events(first_pass)

    with client.stream(
        "GET",
        f"/api/jobs/{job_id}/stream",
        headers={**auth_headers(), "Last-Event-ID": "0"},
    ) as replay:
        events = _read_events(replay)

    gap_events = [e for e in events if e["event"] == "gap"]
    output_events = [e for e in events if e["event"] == "output"]
    assert gap_events, "expected a gap event once seq 0 was evicted from a size-3 ring buffer"
    assert gap_events[0]["data"]["dropped"] > 0
    seqs = [e["data"]["seq"] for e in output_events]
    assert len(set(seqs)) == len(seqs)


def test_stream_and_persisted_output_tail_redact_seeded_secret(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)
    job_id = _create_job(client, lines=3, delay_ms=5, secret=True)

    with client.stream("GET", f"/api/jobs/{job_id}/stream", headers=auth_headers()) as stream:
        events = _read_events(stream)

    output_events = [e for e in events if e["event"] == "output"]
    assert output_events
    assert all(FAKE_SECRET not in e["data"]["line"] for e in output_events)

    record = client.get(f"/api/jobs/{job_id}", headers=auth_headers())
    tail = record.json()["data"]["output_tail"]
    assert tail
    assert all(FAKE_SECRET not in line for line in tail)
    assert FAKE_SECRET not in json.dumps(record.json())


def test_terminal_job_survives_backend_restart_via_sqlite_round_trip(app_factory, tmp_path) -> None:
    storage_path = tmp_path / "cabal-restart.sqlite3"
    app, client = build_client(app_factory, storage_path=storage_path)
    register_fixture_actions(app)
    job_id = _create_job(client, lines=3, delay_ms=5)

    with client.stream("GET", f"/api/jobs/{job_id}/stream", headers=auth_headers()) as stream:
        _read_events(stream)

    before = client.get(f"/api/jobs/{job_id}", headers=auth_headers())
    assert before.json()["data"]["state"] == "succeeded"

    _restarted_app, restarted_client = build_client(
        app_factory,
        storage_path=storage_path,
        handshake_path=tmp_path / "webapi-handshake-2.json",
    )

    after = restarted_client.get(f"/api/jobs/{job_id}", headers=auth_headers())
    assert after.status_code == 200
    assert after.json()["data"]["state"] == "succeeded"
    assert after.json()["data"]["output_tail"] == before.json()["data"]["output_tail"]


def test_exclusive_resource_conflict_returns_409_job_conflict(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)

    first_prepared = client.post(
        "/api/actions/test.job_emitter/prepare",
        json={"lines": 20, "delay_ms": 50, "exclusive_resource": "config.deploy"},
        headers=auth_headers(),
    )
    first_ticket = first_prepared.json()["data"]["ticket_id"]
    first_executed = client.post(
        "/api/actions/test.job_emitter/execute",
        json={"ticket_id": first_ticket},
        headers=auth_headers(),
    )
    assert first_executed.status_code == 202

    second_prepared = client.post(
        "/api/actions/test.job_emitter/prepare",
        json={"lines": 20, "delay_ms": 50, "exclusive_resource": "config.deploy"},
        headers=auth_headers(),
    )
    second_ticket = second_prepared.json()["data"]["ticket_id"]
    second_executed = client.post(
        "/api/actions/test.job_emitter/execute",
        json={"ticket_id": second_ticket},
        headers=auth_headers(),
    )

    assert second_executed.status_code == 409
    body = second_executed.json()
    assert body["error"]["code"] == "job_conflict"
    assert body["error"]["blocking_job_id"] == first_executed.json()["data"]["job_id"]


def test_stream_for_nonexistent_job_returns_404_before_stream_start(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)

    response = client.get("/api/jobs/does-not-exist/stream", headers=auth_headers())

    assert response.status_code == 404
