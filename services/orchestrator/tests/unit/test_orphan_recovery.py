"""Unit tests for ``orchestrator.eventlog.recover_orphans`` (T031).

Pins the orphan-recovery semantics documented in ``data-model.md`` § "Lifecycle"
and the ``run.orphaned`` row of the event-kind matrix, plus FR-013 / SC-007.

A run is considered orphaned by ``recover_orphans(conn, shutdown_marker_ts)``
IFF all three hold:

1. it has at least one ``run.started`` event,
2. it has NO terminal event
   (``run.completed`` / ``run.failed`` / ``run.skipped`` / ``run.orphaned``),
3. the timestamp of its ``run.started`` event is STRICTLY EARLIER than
   ``shutdown_marker_ts``.

When all three hold, ``recover_orphans`` appends one ``run.orphaned`` warn event
with payload ``{"prior_state": "running"}`` for that run and returns the count
of newly-recovered runs. Re-invoking the routine after the orphan event is
already written produces ZERO new events (idempotent).

Per Constitution Principle III these tests land BEFORE the implementation
(T032). Until T032 lands every test is expected to fail with ``ImportError``
on ``recover_orphans``.

Implementer note (T032): tests inject explicit timestamps via the ``ts``
keyword argument on ``append_event``. T013's current signature does not yet
accept ``ts`` — the preferred fix is to extend the signature with an optional
``ts: datetime | None = None`` keyword that defaults to
``datetime.now(timezone.utc)``. This keeps production callers untouched while
letting these tests pin orderings without depending on the system clock.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

from orchestrator.daemon import _notify_orphans
from orchestrator.eventlog import (
    append_event,
    bootstrap,
    connect,
    recover_orphans,
    tail_since,
)


def _seed(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    kind: str,
    ts: datetime,
    level: str = "info",
    payload: dict | None = None,
) -> int:
    new_id = append_event(
        conn,
        run_id=run_id,
        kind=kind,
        level=level,
        payload=payload or {},
        ts=ts,
    )
    conn.commit()
    return new_id


def _orphan_events_for(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, run_id, kind, level, payload_json FROM events "
        "WHERE run_id = ? AND kind = 'run.orphaned' ORDER BY id ASC",
        (run_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def test_running_started_before_marker_is_orphaned(tmp_db: Path) -> None:
    bootstrap(tmp_db)
    marker = datetime.now(UTC)
    started = marker - timedelta(minutes=5)

    with connect(tmp_db) as conn:
        _seed(conn, run_id="run-A", kind="run.queued", ts=started - timedelta(seconds=1))
        _seed(conn, run_id="run-A", kind="run.started", ts=started)

        recovered = recover_orphans(conn, marker)

        orphans = _orphan_events_for(conn, "run-A")

    assert recovered == 1
    assert len(orphans) == 1
    assert orphans[0]["level"] == "warn"
    assert json.loads(orphans[0]["payload_json"]) == {"prior_state": "running"}


def test_completed_run_is_not_orphaned(tmp_db: Path) -> None:
    bootstrap(tmp_db)
    marker = datetime.now(UTC)
    started = marker - timedelta(minutes=5)

    with connect(tmp_db) as conn:
        _seed(conn, run_id="run-A", kind="run.queued", ts=started - timedelta(seconds=1))
        _seed(conn, run_id="run-A", kind="run.started", ts=started)
        _seed(conn, run_id="run-A", kind="run.completed", ts=started + timedelta(seconds=10))

        recovered = recover_orphans(conn, marker)

        orphans = _orphan_events_for(conn, "run-A")

    assert recovered == 0
    assert orphans == []


def test_failed_run_is_not_orphaned(tmp_db: Path) -> None:
    bootstrap(tmp_db)
    marker = datetime.now(UTC)
    started = marker - timedelta(minutes=5)

    with connect(tmp_db) as conn:
        _seed(conn, run_id="run-A", kind="run.queued", ts=started - timedelta(seconds=1))
        _seed(conn, run_id="run-A", kind="run.started", ts=started)
        _seed(
            conn,
            run_id="run-A",
            kind="run.failed",
            level="error",
            ts=started + timedelta(seconds=10),
        )

        recovered = recover_orphans(conn, marker)

        orphans = _orphan_events_for(conn, "run-A")

    assert recovered == 0
    assert orphans == []


def test_skipped_run_is_not_orphaned(tmp_db: Path) -> None:
    bootstrap(tmp_db)
    marker = datetime.now(UTC)
    started = marker - timedelta(minutes=5)

    with connect(tmp_db) as conn:
        _seed(conn, run_id="run-A", kind="run.queued", ts=started - timedelta(seconds=1))
        _seed(conn, run_id="run-A", kind="run.started", ts=started)
        _seed(
            conn,
            run_id="run-A",
            kind="run.skipped",
            level="warn",
            ts=started + timedelta(seconds=10),
        )

        recovered = recover_orphans(conn, marker)

        orphans = _orphan_events_for(conn, "run-A")

    assert recovered == 0
    assert orphans == []


def test_already_orphaned_run_is_not_re_orphaned(tmp_db: Path) -> None:
    bootstrap(tmp_db)
    marker = datetime.now(UTC)
    started = marker - timedelta(minutes=5)

    with connect(tmp_db) as conn:
        _seed(conn, run_id="run-A", kind="run.queued", ts=started - timedelta(seconds=1))
        _seed(conn, run_id="run-A", kind="run.started", ts=started)
        _seed(
            conn,
            run_id="run-A",
            kind="run.orphaned",
            level="warn",
            payload={"prior_state": "running"},
            ts=started + timedelta(seconds=10),
        )

        recovered = recover_orphans(conn, marker)

        orphans = _orphan_events_for(conn, "run-A")

    assert recovered == 0
    assert len(orphans) == 1


def test_recover_orphans_is_idempotent(tmp_db: Path) -> None:
    bootstrap(tmp_db)
    marker = datetime.now(UTC)
    started = marker - timedelta(minutes=5)

    with connect(tmp_db) as conn:
        _seed(conn, run_id="run-A", kind="run.queued", ts=started - timedelta(seconds=1))
        _seed(conn, run_id="run-A", kind="run.started", ts=started)

        first = recover_orphans(conn, marker)
        events_after_first = list(tail_since(conn, last_id=0))

        second = recover_orphans(conn, marker)
        events_after_second = list(tail_since(conn, last_id=0))

    assert first == 1
    assert second == 0
    assert len(events_after_second) == len(events_after_first)


def test_run_started_after_marker_is_not_orphaned(tmp_db: Path) -> None:
    bootstrap(tmp_db)
    marker = datetime.now(UTC)
    started = marker + timedelta(seconds=30)

    with connect(tmp_db) as conn:
        _seed(conn, run_id="run-A", kind="run.queued", ts=marker + timedelta(seconds=10))
        _seed(conn, run_id="run-A", kind="run.started", ts=started)

        recovered = recover_orphans(conn, marker)

        orphans = _orphan_events_for(conn, "run-A")

    assert recovered == 0
    assert orphans == []


def test_run_with_only_queued_is_not_orphaned(tmp_db: Path) -> None:
    bootstrap(tmp_db)
    marker = datetime.now(UTC)
    queued = marker - timedelta(minutes=5)

    with connect(tmp_db) as conn:
        _seed(conn, run_id="run-A", kind="run.queued", ts=queued)

        recovered = recover_orphans(conn, marker)

        orphans = _orphan_events_for(conn, "run-A")

    assert recovered == 0
    assert orphans == []


def test_run_started_at_marker_exactly_is_not_orphaned(tmp_db: Path) -> None:
    """Strict-less-than rule: started_at == marker_ts is NOT an orphan.

    The implementer (T032) honors a strict ``started_at < shutdown_marker_ts``
    comparison so a run that started exactly at the previous shutdown instant
    is treated as belonging to the new daemon, not the old one.
    """
    bootstrap(tmp_db)
    marker = datetime.now(UTC)

    with connect(tmp_db) as conn:
        _seed(conn, run_id="run-A", kind="run.queued", ts=marker - timedelta(seconds=1))
        _seed(conn, run_id="run-A", kind="run.started", ts=marker)

        recovered = recover_orphans(conn, marker)

        orphans = _orphan_events_for(conn, "run-A")

    assert recovered == 0
    assert orphans == []


def test_multiple_orphans_each_get_own_event(tmp_db: Path) -> None:
    bootstrap(tmp_db)
    marker = datetime.now(UTC)
    started = marker - timedelta(minutes=5)

    with connect(tmp_db) as conn:
        for run_id in ("run-A", "run-B", "run-C"):
            _seed(conn, run_id=run_id, kind="run.queued", ts=started - timedelta(seconds=1))
            _seed(conn, run_id=run_id, kind="run.started", ts=started)

        recovered = recover_orphans(conn, marker)

        orphans_a = _orphan_events_for(conn, "run-A")
        orphans_b = _orphan_events_for(conn, "run-B")
        orphans_c = _orphan_events_for(conn, "run-C")

    assert recovered == 3
    assert len(orphans_a) == 1
    assert len(orphans_b) == 1
    assert len(orphans_c) == 1


async def test_NotifyOrphans_NewlyRecoveredRun_PushesWarnNotification(
    tmp_db: Path,
) -> None:
    bootstrap(tmp_db)
    marker = datetime.now(UTC)
    started = marker - timedelta(minutes=5)
    pr_number = 42

    with connect(tmp_db) as conn:
        _seed(
            conn,
            run_id="run-A",
            kind="run.queued",
            ts=started - timedelta(seconds=1),
            payload={
                "repo": "owner/repo",
                "pr_number": pr_number,
                "head_sha": "a" * 40,
                "kind": "pr.review",
            },
        )
        _seed(conn, run_id="run-A", kind="run.started", ts=started)

        last_id_before = conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM events"
        ).fetchone()[0]

        recovered = recover_orphans(conn, marker)
        assert recovered == 1

        notifier = AsyncMock()
        await _notify_orphans(conn, last_id_before, notifier)

    notifier.send.assert_called_once_with(
        level="warn",
        title=f"Orphaned run for PR #{pr_number}",
        body="Daemon restart left a run mid-flight",
    )


def test_mixed_states_only_live_orphans_recovered(tmp_db: Path) -> None:
    bootstrap(tmp_db)
    marker = datetime.now(UTC)
    before = marker - timedelta(minutes=5)
    after = marker + timedelta(seconds=30)

    with connect(tmp_db) as conn:
        _seed(conn, run_id="completed-1", kind="run.queued", ts=before - timedelta(seconds=1))
        _seed(conn, run_id="completed-1", kind="run.started", ts=before)
        _seed(
            conn,
            run_id="completed-1",
            kind="run.completed",
            ts=before + timedelta(seconds=10),
        )

        _seed(conn, run_id="completed-2", kind="run.queued", ts=before - timedelta(seconds=1))
        _seed(conn, run_id="completed-2", kind="run.started", ts=before)
        _seed(
            conn,
            run_id="completed-2",
            kind="run.completed",
            ts=before + timedelta(seconds=10),
        )

        _seed(conn, run_id="live-orphan", kind="run.queued", ts=before - timedelta(seconds=1))
        _seed(conn, run_id="live-orphan", kind="run.started", ts=before)

        _seed(
            conn,
            run_id="already-orphaned",
            kind="run.queued",
            ts=before - timedelta(seconds=1),
        )
        _seed(conn, run_id="already-orphaned", kind="run.started", ts=before)
        _seed(
            conn,
            run_id="already-orphaned",
            kind="run.orphaned",
            level="warn",
            payload={"prior_state": "running"},
            ts=before + timedelta(seconds=5),
        )

        _seed(conn, run_id="just-started", kind="run.queued", ts=marker + timedelta(seconds=5))
        _seed(conn, run_id="just-started", kind="run.started", ts=after)

        recovered = recover_orphans(conn, marker)

        assert recovered == 1
        assert len(_orphan_events_for(conn, "live-orphan")) == 1
        assert _orphan_events_for(conn, "completed-1") == []
        assert _orphan_events_for(conn, "completed-2") == []
        assert len(_orphan_events_for(conn, "already-orphaned")) == 1
        assert _orphan_events_for(conn, "just-started") == []
