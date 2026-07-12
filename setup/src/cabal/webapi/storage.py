"""SQLite persistence for webapi jobs, tickets, audit trail, and diagnostics."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import platformdirs

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    ticket_id TEXT,
    state TEXT NOT NULL,
    output_tail TEXT NOT NULL DEFAULT '[]',
    exit_detail TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    params TEXT NOT NULL,
    effect_preview TEXT NOT NULL,
    precondition_digest TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL,
    ticket_id TEXT,
    job_id TEXT,
    effect_summary TEXT NOT NULL,
    outcome TEXT NOT NULL,
    performed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS diagnostics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    severity TEXT NOT NULL,
    module TEXT NOT NULL,
    message TEXT NOT NULL,
    kind TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
"""

_JOB_FIELDS = (
    "job_id",
    "kind",
    "ticket_id",
    "state",
    "output_tail",
    "exit_detail",
    "created_at",
    "started_at",
    "finished_at",
)


def default_storage_path() -> Path:
    return Path(platformdirs.user_data_dir("cabal", appauthor=False)) / "webapi.sqlite3"


class WriteGuard:
    """Thread-safe counter of persisted writes; backs the zero-write GET-sweep contract."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._count = 0

    @property
    def count(self) -> int:
        with self._lock:
            return self._count

    def increment(self) -> None:
        with self._lock:
            self._count += 1

    def reset(self) -> None:
        with self._lock:
            self._count = 0


class Storage:
    """Lock-guarded SQLite handle with idempotent migrations applied on open."""

    def __init__(self, path: Path | None = None, *, write_guard: WriteGuard | None = None) -> None:
        self.path = Path(path) if path is not None else default_storage_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_guard = write_guard
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            version = self._conn.execute("PRAGMA user_version").fetchone()[0]
            if version < SCHEMA_VERSION:
                self._conn.executescript(_SCHEMA)
                self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _write(self, sql: str, params: tuple) -> int:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
        if self._write_guard is not None:
            self._write_guard.increment()
        return cursor.lastrowid or 0

    def _rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # -- jobs ------------------------------------------------------------

    def save_job(self, record: dict) -> None:
        self._write(
            "INSERT OR REPLACE INTO jobs "
            "(job_id, kind, ticket_id, state, output_tail, exit_detail, created_at, started_at, finished_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record["job_id"],
                record["kind"],
                record.get("ticket_id"),
                record["state"],
                json.dumps(record.get("output_tail", [])),
                record.get("exit_detail"),
                record["created_at"],
                record.get("started_at"),
                record.get("finished_at"),
            ),
        )

    def load_job(self, job_id: str) -> dict | None:
        rows = self._rows("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        return _job_record(rows[0]) if rows else None

    def list_jobs(self) -> list[dict]:
        return [_job_record(row) for row in self._rows("SELECT * FROM jobs ORDER BY created_at")]

    # -- tickets ---------------------------------------------------------

    def save_ticket(self, record: dict) -> None:
        self._write(
            "INSERT OR REPLACE INTO tickets "
            "(ticket_id, action_id, params, effect_preview, precondition_digest, created_at, expires_at, state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record["ticket_id"],
                record["action_id"],
                json.dumps(record["params"]),
                json.dumps(record["effect_preview"]),
                record.get("precondition_digest"),
                record["created_at"],
                record["expires_at"],
                record["state"],
            ),
        )

    def load_ticket(self, ticket_id: str) -> dict | None:
        rows = self._rows("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
        if not rows:
            return None
        record = dict(rows[0])
        record["params"] = json.loads(record["params"])
        record["effect_preview"] = json.loads(record["effect_preview"])
        return record

    def set_ticket_state(self, ticket_id: str, state: str) -> None:
        self._write("UPDATE tickets SET state = ? WHERE ticket_id = ?", (state, ticket_id))

    # -- audit -----------------------------------------------------------

    def add_audit(self, entry: dict) -> int:
        return self._write(
            "INSERT INTO audit (action_id, ticket_id, job_id, effect_summary, outcome, performed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry["action_id"],
                entry.get("ticket_id"),
                entry.get("job_id"),
                entry["effect_summary"],
                entry["outcome"],
                entry["performed_at"],
            ),
        )

    def list_audit(self) -> list[dict]:
        return [dict(row) for row in self._rows("SELECT * FROM audit ORDER BY id")]

    # -- diagnostics -----------------------------------------------------

    def add_diagnostic(self, event: dict) -> int:
        return self._write(
            "INSERT INTO diagnostics (severity, module, message, kind, occurred_at) VALUES (?, ?, ?, ?, ?)",
            (
                event["severity"],
                event["module"],
                event["message"],
                event["kind"],
                event["occurred_at"],
            ),
        )

    def list_diagnostics(self, limit: int | None = None, severity: str | None = None) -> list[dict]:
        sql = "SELECT * FROM diagnostics"
        params: tuple = ()
        if severity is not None:
            sql += " WHERE severity = ?"
            params = (severity,)
        sql += " ORDER BY id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params = (*params, int(limit))
        return [dict(row) for row in self._rows(sql, params)]


def _job_record(row: sqlite3.Row) -> dict:
    record = dict(row)
    record["output_tail"] = json.loads(record["output_tail"])
    return record
