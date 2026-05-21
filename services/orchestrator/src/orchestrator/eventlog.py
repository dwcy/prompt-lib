"""SQLite-backed append-only event log (T013).

Per research.md R6 and data-model.md § "SQLite schema (DDL)":

* Single-writer (the daemon) + multiple-reader (the dashboard) pattern.
* WAL journal mode + ``synchronous = NORMAL`` for non-blocking reads.
* Append-only ``events`` table; run state is derived per ``run_id`` from the
  latest event.
* ``cursor`` table holds the polling-trigger bookmark per PR.

All functions are synchronous. SQLite I/O is sub-millisecond locally; calling
these from an async daemon is fine without a thread-pool wrapper.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

_logger = logging.getLogger(__name__)

Level = Literal["info", "warn", "error", "needs_input"]
RunState = Literal["pending", "running", "completed", "failed", "skipped", "orphaned"]

_SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT    NOT NULL,
    run_id       TEXT    NOT NULL,
    kind         TEXT    NOT NULL,
    level        TEXT    NOT NULL CHECK (level IN ('info','warn','error','needs_input')),
    payload_json TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS events_by_run ON events (run_id, id);
CREATE INDEX IF NOT EXISTS events_by_ts  ON events (ts);

CREATE TABLE IF NOT EXISTS cursor (
    pr_number  INTEGER PRIMARY KEY,
    head_sha   TEXT    NOT NULL,
    last_seen  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS worktrees (
    key            TEXT PRIMARY KEY,
    path           TEXT NOT NULL,
    ref            TEXT NOT NULL,
    created_at     INTEGER NOT NULL,
    last_used_at   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS worktrees_by_last_used ON worktrees (last_used_at);

CREATE TABLE IF NOT EXISTS issue_cursor (
    issue_number INTEGER PRIMARY KEY,
    repo         TEXT    NOT NULL,
    triaged_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""

_TERMINAL_KINDS: dict[str, RunState] = {
    "run.completed": "completed",
    "run.failed": "failed",
    "run.skipped": "skipped",
    "run.orphaned": "orphaned",
}


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    ts: str
    run_id: str
    kind: str
    level: Level
    payload_json: str


class Cursor(BaseModel):
    model_config = ConfigDict(frozen=True)

    pr_number: int
    head_sha: str
    last_seen: str


class Run(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    kind: str | None
    repo: str | None
    pr_number: int | None
    head_sha: str | None
    state: RunState
    started_at: str | None
    ended_at: str | None
    artifact_url: str | None


def bootstrap(path: Path) -> None:
    """Create the database file and schema if missing.

    Idempotent: safe to call on every daemon start. Creates parent directories
    if they do not exist. Enables WAL journal mode and ``synchronous = NORMAL``
    so single-writer + multi-reader concurrency works without locking.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.executescript(_DDL)
        existing = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
        if existing == 0:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (_SCHEMA_VERSION,),
            )
        conn.commit()
    finally:
        conn.close()


def connect(path: Path) -> sqlite3.Connection:
    """Open a connection to an already-bootstrapped database."""
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def append_event(
    conn: sqlite3.Connection,
    *,
    run_id: str | UUID,
    kind: str,
    level: Level = "info",
    payload: dict[str, Any] | None = None,
    ts: datetime | None = None,
) -> int:
    """Insert one event row; return its new auto-increment id.

    Sets ``ts`` to the current UTC instant in ISO 8601 unless an explicit
    ``ts`` value is provided (used by orphan-recovery tests to pin orderings
    without depending on the system clock). JSON-encodes ``payload`` as UTF-8
    text. The ``level`` CHECK constraint at the SQLite layer rejects unknown
    levels with ``sqlite3.IntegrityError``.
    """
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    ts_str = (ts if ts is not None else datetime.now(UTC)).isoformat()
    cursor = conn.execute(
        "INSERT INTO events (ts, run_id, kind, level, payload_json) VALUES (?, ?, ?, ?, ?)",
        (ts_str, str(run_id), kind, level, payload_json),
    )
    new_id = cursor.lastrowid
    if new_id is None:
        raise RuntimeError("sqlite did not return a lastrowid for events insert")
    return int(new_id)


def recover_orphans(conn: sqlite3.Connection, shutdown_marker_ts: datetime) -> int:
    """Emit one ``run.orphaned`` event for each run left mid-flight by a prior daemon.

    A run qualifies as orphaned IFF all three hold (per data-model.md § Lifecycle
    and FR-013 / SC-007):

    1. it has at least one ``run.started`` event,
    2. it has NO terminal event (``run.completed`` / ``run.failed`` /
       ``run.skipped`` / ``run.orphaned``),
    3. its earliest ``run.started`` ts is STRICTLY EARLIER than
       ``shutdown_marker_ts``.

    Pure with respect to the eventlog: writes ``run.orphaned`` events only,
    never reads or writes the marker file (that is the daemon's job). Safe to
    re-invoke — already-orphaned runs are skipped because ``run.orphaned`` is
    itself a terminal kind. Returns the number of events written in this call.
    """
    rows = conn.execute(
        "SELECT run_id, kind, ts FROM events ORDER BY run_id, id ASC",
    ).fetchall()

    by_run: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_run.setdefault(row["run_id"], []).append(row)

    marker_iso = shutdown_marker_ts.isoformat()
    orphaned_run_ids: list[str] = []
    for run_id, run_rows in by_run.items():
        kinds_seen = {r["kind"] for r in run_rows}
        if "run.started" not in kinds_seen:
            continue
        if any(kind in _TERMINAL_KINDS for kind in kinds_seen):
            continue
        started_ts: str | None = next(
            (r["ts"] for r in run_rows if r["kind"] == "run.started"),
            None,
        )
        if started_ts is None or started_ts >= marker_iso:
            continue
        orphaned_run_ids.append(run_id)

    if not orphaned_run_ids:
        return 0

    with conn:
        for run_id in orphaned_run_ids:
            append_event(
                conn,
                run_id=run_id,
                kind="run.orphaned",
                level="warn",
                payload={"prior_state": "running"},
            )
    return len(orphaned_run_ids)


def write_shutdown_marker(path: Path) -> None:
    """Atomically write the current UTC timestamp (ISO 8601) to ``path``.

    Used by the daemon on graceful shutdown so the next start can recover any
    runs left in ``running`` state by an unclean termination. Writes to a
    sibling ``.tmp`` file then renames over the target so a crash mid-write
    cannot leave a half-written marker.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(datetime.now(UTC).isoformat(), encoding="utf-8")
    os.replace(tmp_path, path)


def read_shutdown_marker(path: Path) -> datetime | None:
    """Return the parsed marker timestamp, or ``None`` if missing or unparseable.

    Logs a warning when the file exists but cannot be parsed so an operator
    sees the corruption without the daemon refusing to start.
    """
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        _logger.warning("failed to read shutdown marker at %s: %s", path, exc)
        return None
    if not raw:
        _logger.warning("shutdown marker at %s is empty", path)
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        _logger.warning("shutdown marker at %s is unparseable (%s): %r", path, exc, raw)
        return None


def tail_since(conn: sqlite3.Connection, last_id: int) -> list[Event]:
    """Return events with ``id > last_id`` in ascending id order."""
    rows = conn.execute(
        "SELECT id, ts, run_id, kind, level, payload_json "
        "FROM events WHERE id > ? ORDER BY id ASC",
        (last_id,),
    ).fetchall()
    return [
        Event(
            id=row["id"],
            ts=row["ts"],
            run_id=row["run_id"],
            kind=row["kind"],
            level=row["level"],
            payload_json=row["payload_json"],
        )
        for row in rows
    ]


def cursor_get(conn: sqlite3.Connection, pr_number: int) -> Cursor | None:
    """Look up the polling cursor row for ``pr_number``."""
    row = conn.execute(
        "SELECT pr_number, head_sha, last_seen FROM cursor WHERE pr_number = ?",
        (pr_number,),
    ).fetchone()
    if row is None:
        return None
    return Cursor(
        pr_number=row["pr_number"],
        head_sha=row["head_sha"],
        last_seen=row["last_seen"],
    )


def cursor_upsert(
    conn: sqlite3.Connection,
    pr_number: int,
    head_sha: str,
    *,
    last_seen: datetime | str,
) -> None:
    """Insert or replace the polling cursor row for ``pr_number``.

    ``last_seen`` is normalized to an ISO 8601 string for storage. Other
    cursor rows are not touched.
    """
    last_seen_str = last_seen.isoformat() if isinstance(last_seen, datetime) else last_seen
    conn.execute(
        "INSERT INTO cursor (pr_number, head_sha, last_seen) VALUES (?, ?, ?) "
        "ON CONFLICT(pr_number) DO UPDATE SET "
        "head_sha = excluded.head_sha, last_seen = excluded.last_seen",
        (pr_number, head_sha, last_seen_str),
    )


def issue_cursor_is_triaged(conn: sqlite3.Connection, issue_number: int, repo: str) -> bool:
    """Return True if ``issue_number`` has already been successfully triaged for ``repo``."""
    row = conn.execute(
        "SELECT 1 FROM issue_cursor WHERE issue_number = ? AND repo = ?",
        (issue_number, repo),
    ).fetchone()
    return row is not None


def issue_cursor_mark_triaged(
    conn: sqlite3.Connection,
    issue_number: int,
    repo: str,
    *,
    ts: datetime | None = None,
) -> None:
    """Insert or replace the triage-completion record for ``issue_number``."""
    ts_str = (ts if ts is not None else datetime.now(UTC)).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO issue_cursor (issue_number, repo, triaged_at) VALUES (?, ?, ?)",
        (issue_number, repo, ts_str),
    )


def runs_summary(conn: sqlite3.Connection) -> list[Run]:
    """Derive per-run state from the events table.

    State derivation per data-model.md state machine: terminal kinds
    (``run.completed | run.failed | run.skipped | run.orphaned``) take
    precedence over ``run.started`` (running) which takes precedence over
    ``run.queued`` (pending). Repo / pr_number / head_sha are pulled from the
    ``run.queued`` payload when available.
    """
    rows = conn.execute(
        "SELECT id, run_id, kind, ts, payload_json FROM events ORDER BY run_id, id ASC"
    ).fetchall()

    by_run: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_run.setdefault(row["run_id"], []).append(row)

    summary: list[Run] = []
    for run_id, run_rows in by_run.items():
        kinds_seen = {r["kind"] for r in run_rows}

        state: RunState = "pending"
        for kind, mapped in _TERMINAL_KINDS.items():
            if kind in kinds_seen:
                state = mapped
                break
        else:
            if "run.started" in kinds_seen:
                state = "running"
            elif "run.queued" in kinds_seen:
                state = "pending"

        queued_payload: dict[str, Any] = {}
        for r in run_rows:
            if r["kind"] == "run.queued":
                queued_payload = json.loads(r["payload_json"])
                break

        started_at: str | None = None
        for r in run_rows:
            if r["kind"] == "run.started":
                started_at = r["ts"]
                break

        ended_at: str | None = None
        artifact_url: str | None = None
        for r in run_rows:
            if r["kind"] in _TERMINAL_KINDS:
                ended_at = r["ts"]
                terminal_payload = json.loads(r["payload_json"])
                artifact_url = terminal_payload.get("artifact_url")
                break

        summary.append(
            Run(
                run_id=run_id,
                kind=queued_payload.get("kind"),
                repo=queued_payload.get("repo"),
                pr_number=queued_payload.get("pr_number"),
                head_sha=queued_payload.get("head_sha"),
                state=state,
                started_at=started_at,
                ended_at=ended_at,
                artifact_url=artifact_url,
            )
        )

    return summary
