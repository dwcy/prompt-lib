from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  channel     TEXT NOT NULL,
  from_agent  TEXT NOT NULL,
  content     TEXT NOT NULL,
  metadata    TEXT NOT NULL DEFAULT '{}',
  created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_channel_id ON messages(channel, id);

CREATE TABLE IF NOT EXISTS memory (
  namespace   TEXT NOT NULL,
  key         TEXT NOT NULL,
  value       TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  PRIMARY KEY (namespace, key)
);

CREATE TABLE IF NOT EXISTS agents (
  name           TEXT PRIMARY KEY,
  capabilities   TEXT NOT NULL DEFAULT '[]',
  last_heartbeat TEXT NOT NULL
);
"""


def db_path() -> Path:
    return Path.home() / ".claude" / "mcp-bus" / "bus.db"


def ensure_db(path: Path | None = None) -> Path:
    target = path if path is not None else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(target)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        conn.commit()
    return target
