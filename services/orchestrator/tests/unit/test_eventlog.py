"""Unit tests for ``orchestrator.eventlog`` (T012).

Pins the SQLite schema bootstrap, append-only event semantics, the
``runs_summary`` derivation logic, the ``cursor`` upsert behaviour, and
WAL-mode reader/writer concurrency documented in ``data-model.md``.

Per Constitution Principle III these tests land BEFORE the implementation
(T013); until then every test is expected to fail with ``ImportError`` on
``orchestrator.eventlog``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest


def _import_eventlog():
    from orchestrator import eventlog

    return eventlog


def _open_raw(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _append(
    eventlog,
    conn: sqlite3.Connection,
    *,
    run_id: str,
    kind: str,
    level: str = "info",
    payload: dict[str, Any] | None = None,
) -> int:
    return eventlog.append_event(
        conn,
        run_id=run_id,
        kind=kind,
        level=level,
        payload=payload or {},
    )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


class TestBootstrap:
    def test_bootstrap_creates_db_file(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()

        eventlog.bootstrap(tmp_db)

        assert tmp_db.exists()

    def test_bootstrap_is_idempotent(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()

        eventlog.bootstrap(tmp_db)
        eventlog.bootstrap(tmp_db)

        assert tmp_db.exists()

    def test_bootstrap_enables_wal_journal_mode(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()

        eventlog.bootstrap(tmp_db)
        with _open_raw(tmp_db) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]

        assert mode.lower() == "wal"

    def test_bootstrap_creates_three_tables(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()

        eventlog.bootstrap(tmp_db)
        with _open_raw(tmp_db) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()

        names = {row["name"] for row in rows}
        assert {"events", "cursor", "schema_version"}.issubset(names)

    def test_bootstrap_inserts_single_schema_version_row(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()

        eventlog.bootstrap(tmp_db)
        with _open_raw(tmp_db) as conn:
            rows = conn.execute("SELECT version FROM schema_version").fetchall()

        assert len(rows) == 1
        assert rows[0]["version"] == 1

    def test_idempotent_bootstrap_does_not_duplicate_schema_version(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()

        eventlog.bootstrap(tmp_db)
        eventlog.bootstrap(tmp_db)
        with _open_raw(tmp_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]

        assert count == 1


# ---------------------------------------------------------------------------
# append_event
# ---------------------------------------------------------------------------


class TestAppendEvent:
    def test_append_returns_new_row_id(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn:
            new_id = _append(
                eventlog,
                conn,
                run_id="run-A",
                kind="run.queued",
                payload={"repo": "owner/repo", "pr_number": 1},
            )
            conn.commit()

        assert isinstance(new_id, int)
        assert new_id > 0

    def test_append_stores_payload_as_json(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)
        payload = {"repo": "owner/repo", "pr_number": 7, "head_sha": "a" * 40}

        with _open_raw(tmp_db) as conn:
            new_id = _append(eventlog, conn, run_id="run-A", kind="run.queued", payload=payload)
            conn.commit()
            row = conn.execute(
                "SELECT run_id, kind, level, payload_json FROM events WHERE id = ?",
                (new_id,),
            ).fetchone()

        assert row["run_id"] == "run-A"
        assert row["kind"] == "run.queued"
        assert row["level"] == "info"
        assert json.loads(row["payload_json"]) == payload

    def test_consecutive_appends_have_monotonic_ids(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn:
            id_one = _append(eventlog, conn, run_id="run-A", kind="run.queued")
            id_two = _append(eventlog, conn, run_id="run-A", kind="run.started")
            conn.commit()

        assert id_two > id_one

    def test_invalid_level_rejected_by_check_constraint(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn, pytest.raises(sqlite3.IntegrityError):
            _append(eventlog, conn, run_id="run-A", kind="run.queued", level="bogus")
            conn.commit()


# ---------------------------------------------------------------------------
# tail_since
# ---------------------------------------------------------------------------


class TestTailSince:
    def test_returns_empty_when_no_events(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn:
            result = eventlog.tail_since(conn, last_id=0)

        assert list(result) == []

    def test_returns_full_set_when_last_id_is_zero(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn:
            _append(eventlog, conn, run_id="run-A", kind="run.queued")
            _append(eventlog, conn, run_id="run-A", kind="run.started")
            _append(eventlog, conn, run_id="run-A", kind="run.completed")
            conn.commit()
            result = list(eventlog.tail_since(conn, last_id=0))

        assert len(result) == 3

    def test_returns_only_rows_with_id_greater_than_last_id(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn:
            id_one = _append(eventlog, conn, run_id="run-A", kind="run.queued")
            id_two = _append(eventlog, conn, run_id="run-A", kind="run.started")
            id_three = _append(eventlog, conn, run_id="run-A", kind="run.completed")
            conn.commit()

            result = list(eventlog.tail_since(conn, last_id=id_one))

        ids = [row.id for row in result]
        assert ids == [id_two, id_three]

    def test_returns_empty_when_no_rows_newer_than_last_id(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn:
            last = _append(eventlog, conn, run_id="run-A", kind="run.queued")
            conn.commit()
            result = list(eventlog.tail_since(conn, last_id=last))

        assert result == []

    def test_results_ordered_ascending_by_id(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn:
            _append(eventlog, conn, run_id="run-A", kind="run.queued")
            _append(eventlog, conn, run_id="run-B", kind="run.queued")
            _append(eventlog, conn, run_id="run-A", kind="run.started")
            conn.commit()
            result = list(eventlog.tail_since(conn, last_id=0))

        ids = [row.id for row in result]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# cursor
# ---------------------------------------------------------------------------


class TestCursor:
    def test_cursor_get_returns_none_when_missing(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn:
            result = eventlog.cursor_get(conn, pr_number=42)

        assert result is None

    def test_cursor_upsert_inserts_when_missing(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)
        sha = "a" * 40

        with _open_raw(tmp_db) as conn:
            eventlog.cursor_upsert(
                conn, pr_number=42, head_sha=sha, last_seen="2026-05-10T12:00:00Z"
            )
            conn.commit()
            row = eventlog.cursor_get(conn, pr_number=42)

        assert row is not None
        assert row.pr_number == 42
        assert row.head_sha == sha

    def test_cursor_upsert_updates_when_present(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)
        sha_one = "a" * 40
        sha_two = "b" * 40

        with _open_raw(tmp_db) as conn:
            eventlog.cursor_upsert(
                conn, pr_number=42, head_sha=sha_one, last_seen="2026-05-10T12:00:00Z"
            )
            eventlog.cursor_upsert(
                conn, pr_number=42, head_sha=sha_two, last_seen="2026-05-10T13:00:00Z"
            )
            conn.commit()
            row = eventlog.cursor_get(conn, pr_number=42)

        assert row is not None
        assert row.head_sha == sha_two

    def test_cursor_upsert_keeps_other_rows_intact(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn:
            eventlog.cursor_upsert(
                conn, pr_number=1, head_sha="a" * 40, last_seen="2026-05-10T12:00:00Z"
            )
            eventlog.cursor_upsert(
                conn, pr_number=2, head_sha="b" * 40, last_seen="2026-05-10T12:00:00Z"
            )
            eventlog.cursor_upsert(
                conn, pr_number=2, head_sha="c" * 40, last_seen="2026-05-10T13:00:00Z"
            )
            conn.commit()
            row_one = eventlog.cursor_get(conn, pr_number=1)
            row_two = eventlog.cursor_get(conn, pr_number=2)

        assert row_one is not None and row_one.head_sha == "a" * 40
        assert row_two is not None and row_two.head_sha == "c" * 40


# ---------------------------------------------------------------------------
# runs_summary
# ---------------------------------------------------------------------------


def _seed_run(
    eventlog,
    conn: sqlite3.Connection,
    run_id: str,
    event_kinds: list[str],
) -> None:
    for kind in event_kinds:
        level = "error" if kind == "run.failed" else "warn" if kind in {
            "run.skipped",
            "run.orphaned",
        } else "info"
        _append(eventlog, conn, run_id=run_id, kind=kind, level=level)


class TestRunsSummary:
    def test_empty_when_no_events(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn:
            result = eventlog.runs_summary(conn)

        assert list(result) == []

    def test_states_derived_from_latest_terminal_event_per_run(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        runs: dict[str, list[str]] = {
            "run-A": ["run.queued"],
            "run-B": ["run.queued", "run.started"],
            "run-C": ["run.queued", "run.started", "run.completed"],
            "run-D": ["run.queued", "run.started", "run.failed"],
            "run-E": ["run.queued", "run.started", "run.skipped"],
            "run-F": ["run.queued", "run.started", "run.orphaned"],
        }
        expected_states = {
            "run-A": "pending",
            "run-B": "running",
            "run-C": "completed",
            "run-D": "failed",
            "run-E": "skipped",
            "run-F": "orphaned",
        }

        with _open_raw(tmp_db) as conn:
            for run_id, kinds in runs.items():
                _seed_run(eventlog, conn, run_id, kinds)
            conn.commit()
            summary = list(eventlog.runs_summary(conn))

        by_run_id = {run.run_id: run.state for run in summary}
        assert by_run_id == expected_states

    def test_one_run_entry_per_distinct_run_id(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        with _open_raw(tmp_db) as conn:
            _seed_run(eventlog, conn, "run-A", ["run.queued", "run.started", "run.completed"])
            _seed_run(eventlog, conn, "run-B", ["run.queued", "run.started"])
            conn.commit()
            summary = list(eventlog.runs_summary(conn))

        assert len({run.run_id for run in summary}) == 2


# ---------------------------------------------------------------------------
# Concurrent reader sees committed writer (WAL)
# ---------------------------------------------------------------------------


class TestConcurrentReader:
    def test_reader_sees_writer_row_after_commit(self, tmp_db: Path) -> None:
        eventlog = _import_eventlog()
        eventlog.bootstrap(tmp_db)

        writer = _open_raw(tmp_db)
        reader = _open_raw(tmp_db)
        try:
            new_id = _append(eventlog, writer, run_id="run-A", kind="run.queued")
            writer.commit()

            tail = list(eventlog.tail_since(reader, last_id=0))

            assert any(row.id == new_id for row in tail)
        finally:
            writer.close()
            reader.close()
