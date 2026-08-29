"""SQLite persistence for webapi jobs, tickets, audit trail, and diagnostics."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

import platformdirs

from cabal.webapi.security import restrict_to_owner

SCHEMA_VERSION = 3

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
CREATE TABLE IF NOT EXISTS supervised_runs (
    exclusive_resource TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    run_id TEXT NOT NULL,
    pid INTEGER,
    artifact_root TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS news_source_preferences (
    source_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS news_item_state (
    item_id TEXT PRIMARY KEY,
    is_read INTEGER NOT NULL DEFAULT 0,
    is_saved INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
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
        # Tickets can hold caller-supplied params; the DB gets the same
        # owner-only protection as the handshake file, and params left behind
        # by a previous run are purged before anything is served.
        restrict_to_owner(self.path)
        self._purge_stale_ticket_params()

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
        if state == "pending":
            self._write("UPDATE tickets SET state = ? WHERE ticket_id = ?", (state, ticket_id))
        else:
            # Terminal states never need the params again; drop them so
            # consumed tickets don't retain caller-supplied values on disk.
            self._write(
                "UPDATE tickets SET state = ?, params = '{}' WHERE ticket_id = ?",
                (state, ticket_id),
            )

    def consume_ticket(self, ticket_id: str) -> bool:
        """Atomically flip a pending ticket to executed; False when it was not pending.

        The conditional UPDATE is the single-use guarantee: of N concurrent
        executes for one ticket, exactly one observes rowcount == 1.
        Params are kept so a conflict-released claim can retry.
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE tickets SET state = 'executed' WHERE ticket_id = ? AND state = 'pending'",
                (ticket_id,),
            )
            self._conn.commit()
        if self._write_guard is not None:
            self._write_guard.increment()
        return cursor.rowcount == 1

    def clear_ticket_params(self, ticket_id: str) -> None:
        self._write("UPDATE tickets SET params = '{}' WHERE ticket_id = ?", (ticket_id,))

    def _purge_stale_ticket_params(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                "UPDATE tickets SET params = '{}' WHERE state != 'pending' OR expires_at < ?",
                (now,),
            )
            self._conn.commit()

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

    # -- supervised runs (021-codegen-eval-modules, data-model B1) -------

    def save_supervised_run(self, record: dict) -> None:
        """One row per `exclusive_resource`, replaced on each launch.

        This is the durable side of `run_supervisor.SupervisedRun` -- the handle itself
        is deliberately ephemeral (research.md R1/R2), but a bare `pid` has to survive a
        backend restart for the post-restart exclusive-resource liveness check
        (research.md R7) to find a still-live detached run again; nothing else records
        a run's pid anywhere (`.dotnetgen/runs/<id>.json` and `evals/results/<id>/run.json`
        do not carry one).
        """
        self._write(
            "INSERT OR REPLACE INTO supervised_runs "
            "(exclusive_resource, job_id, kind, run_id, pid, artifact_root, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record["exclusive_resource"],
                record["job_id"],
                record["kind"],
                record["run_id"],
                record.get("pid"),
                record["artifact_root"],
                record["created_at"],
            ),
        )

    def load_supervised_run(self, exclusive_resource: str) -> dict | None:
        rows = self._rows(
            "SELECT * FROM supervised_runs WHERE exclusive_resource = ?", (exclusive_resource,)
        )
        return dict(rows[0]) if rows else None

    def delete_supervised_run(self, exclusive_resource: str) -> None:
        self._write(
            "DELETE FROM supervised_runs WHERE exclusive_resource = ?", (exclusive_resource,)
        )

    # -- news feed preferences -----------------------------------------

    def list_news_source_preferences(self) -> dict[str, bool]:
        return {row["source_id"]: bool(row["enabled"]) for row in self._rows("SELECT source_id, enabled FROM news_source_preferences")}

    def set_news_source_enabled(self, source_id: str, enabled: bool, updated_at: str) -> None:
        self._write(
            "INSERT OR REPLACE INTO news_source_preferences (source_id, enabled, updated_at) VALUES (?, ?, ?)",
            (source_id, int(enabled), updated_at),
        )

    def list_news_item_states(self) -> dict[str, dict[str, bool]]:
        return {row["item_id"]: {"read": bool(row["is_read"]), "saved": bool(row["is_saved"])} for row in self._rows("SELECT item_id, is_read, is_saved FROM news_item_state")}

    def set_news_item_state(self, item_id: str, *, read: bool | None = None, saved: bool | None = None, updated_at: str) -> None:
        current = self.list_news_item_states().get(item_id, {"read": False, "saved": False})
        self._write(
            "INSERT OR REPLACE INTO news_item_state (item_id, is_read, is_saved, updated_at) VALUES (?, ?, ?, ?)",
            (item_id, int(current["read"] if read is None else read), int(current["saved"] if saved is None else saved), updated_at),
        )


def _job_record(row: sqlite3.Row) -> dict:
    record = dict(row)
    record["output_tail"] = json.loads(record["output_tail"])
    return record
