from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_bus.paths import db_path

READ_LIMIT_MAX = 100


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def _connect(path: Path | None) -> Iterator[sqlite3.Connection]:
    # sqlite3's own context manager commits but never closes — close explicitly
    # so a long-running stdio server does not leak a connection per tool call.
    conn = sqlite3.connect(path if path is not None else db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def post_message(
    channel: str,
    content: str,
    from_agent: str,
    metadata: dict[str, Any] | None = None,
    *,
    path: Path | None = None,
) -> int:
    payload = json.dumps(metadata if metadata is not None else {})
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO messages (channel, from_agent, content, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (channel, from_agent, content, payload, _now()),
        )
        return int(cur.lastrowid)


def read_messages(
    channel: str,
    since_id: int | None = None,
    limit: int = 20,
    *,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    capped = max(1, min(limit, READ_LIMIT_MAX))
    cursor = since_id if since_id is not None else 0
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT id, channel, from_agent, content, metadata, created_at "
            "FROM messages WHERE channel = ? AND id > ? ORDER BY id ASC LIMIT ?",
            (channel, cursor, capped),
        ).fetchall()
    return [
        {
            "message_id": row["id"],
            "channel": row["channel"],
            "from_agent": row["from_agent"],
            "content": row["content"],
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def list_channels(*, path: Path | None = None) -> list[str]:
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT channel FROM messages ORDER BY channel ASC"
        ).fetchall()
    return [row["channel"] for row in rows]


def mem_set(namespace: str, key: str, value: str, *, path: Path | None = None) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO memory (namespace, key, value, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(namespace, key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            (namespace, key, value, _now()),
        )


def mem_get(namespace: str, key: str, *, path: Path | None = None) -> str | None:
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT value FROM memory WHERE namespace = ? AND key = ?",
            (namespace, key),
        ).fetchone()
    return row["value"] if row is not None else None


def mem_list(namespace: str, *, path: Path | None = None) -> list[str]:
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT key FROM memory WHERE namespace = ? ORDER BY key ASC",
            (namespace,),
        ).fetchall()
    return [row["key"] for row in rows]


def mem_delete(namespace: str, key: str, *, path: Path | None = None) -> None:
    with _connect(path) as conn:
        conn.execute(
            "DELETE FROM memory WHERE namespace = ? AND key = ?",
            (namespace, key),
        )


def agent_register(
    name: str,
    capabilities: list[str],
    *,
    path: Path | None = None,
) -> None:
    payload = json.dumps(capabilities)
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO agents (name, capabilities, last_heartbeat) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET capabilities = excluded.capabilities, "
            "last_heartbeat = excluded.last_heartbeat",
            (name, payload, _now()),
        )


def agent_list(*, path: Path | None = None) -> list[dict[str, Any]]:
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT name, capabilities, last_heartbeat FROM agents ORDER BY name ASC"
        ).fetchall()
    return [
        {
            "name": row["name"],
            "capabilities": json.loads(row["capabilities"]),
            "last_heartbeat": row["last_heartbeat"],
        }
        for row in rows
    ]


def agent_heartbeat(name: str, *, path: Path | None = None) -> None:
    with _connect(path) as conn:
        cur = conn.execute(
            "UPDATE agents SET last_heartbeat = ? WHERE name = ?",
            (_now(), name),
        )
        if cur.rowcount == 0:
            raise ValueError(f"agent '{name}' is not registered")
