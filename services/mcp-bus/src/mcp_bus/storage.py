from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp_bus.paths import db_path

READ_LIMIT_MAX = 100
NAME_MAX_CHARS = 128
CONTENT_MAX_BYTES = 64 * 1024
METADATA_MAX_BYTES = 16 * 1024
MEMORY_VALUE_MAX_BYTES = 64 * 1024
CAPABILITIES_MAX_BYTES = 16 * 1024
CHANNEL_RETENTION_MAX = 10_000


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_text(name: str, value: str, *, max_chars: int, allow_empty: bool = False) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if not allow_empty and not value:
        raise ValueError(f"{name} must not be empty")
    if len(value) > max_chars:
        raise ValueError(f"{name} must be at most {max_chars} characters")


def _require_utf8_size(name: str, value: str, *, max_bytes: int) -> None:
    size = len(value.encode("utf-8"))
    if size > max_bytes:
        raise ValueError(f"{name} must be at most {max_bytes} bytes")


def _json_payload(name: str, value: Any, *, max_bytes: int) -> str:
    try:
        payload = json.dumps(value, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON-serializable") from exc
    _require_utf8_size(name, payload, max_bytes=max_bytes)
    return payload


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
    _require_text("channel", channel, max_chars=NAME_MAX_CHARS)
    _require_text("from_agent", from_agent, max_chars=NAME_MAX_CHARS)
    _require_utf8_size("content", content, max_bytes=CONTENT_MAX_BYTES)
    payload = _json_payload(
        "metadata",
        metadata if metadata is not None else {},
        max_bytes=METADATA_MAX_BYTES,
    )
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO messages (channel, from_agent, content, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (channel, from_agent, content, payload, _now()),
        )
        _prune_channel(conn, channel, CHANNEL_RETENTION_MAX)
        return int(cur.lastrowid)


def read_messages(
    channel: str,
    since_id: int | None = None,
    limit: int = 20,
    *,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    _require_text("channel", channel, max_chars=NAME_MAX_CHARS)
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
    _require_text("namespace", namespace, max_chars=NAME_MAX_CHARS)
    _require_text("key", key, max_chars=NAME_MAX_CHARS)
    _require_utf8_size("value", value, max_bytes=MEMORY_VALUE_MAX_BYTES)
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO memory (namespace, key, value, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(namespace, key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            (namespace, key, value, _now()),
        )


def mem_get(namespace: str, key: str, *, path: Path | None = None) -> str | None:
    _require_text("namespace", namespace, max_chars=NAME_MAX_CHARS)
    _require_text("key", key, max_chars=NAME_MAX_CHARS)
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT value FROM memory WHERE namespace = ? AND key = ?",
            (namespace, key),
        ).fetchone()
    return row["value"] if row is not None else None


def mem_list(namespace: str, *, path: Path | None = None) -> list[str]:
    _require_text("namespace", namespace, max_chars=NAME_MAX_CHARS)
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT key FROM memory WHERE namespace = ? ORDER BY key ASC",
            (namespace,),
        ).fetchall()
    return [row["key"] for row in rows]


def mem_delete(namespace: str, key: str, *, path: Path | None = None) -> None:
    _require_text("namespace", namespace, max_chars=NAME_MAX_CHARS)
    _require_text("key", key, max_chars=NAME_MAX_CHARS)
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
    _require_text("name", name, max_chars=NAME_MAX_CHARS)
    payload = _json_payload("capabilities", capabilities, max_bytes=CAPABILITIES_MAX_BYTES)
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
    _require_text("name", name, max_chars=NAME_MAX_CHARS)
    with _connect(path) as conn:
        cur = conn.execute(
            "UPDATE agents SET last_heartbeat = ? WHERE name = ?",
            (_now(), name),
        )
        if cur.rowcount == 0:
            raise ValueError(f"agent '{name}' is not registered")


def _prune_channel(conn: sqlite3.Connection, channel: str, keep_last: int) -> int:
    if keep_last < 1:
        raise ValueError("keep_last must be >= 1")
    threshold = conn.execute(
        "SELECT id FROM messages WHERE channel = ? ORDER BY id DESC LIMIT 1 OFFSET ?",
        (channel, keep_last - 1),
    ).fetchone()
    if threshold is None:
        return 0
    cur = conn.execute(
        "DELETE FROM messages WHERE channel = ? AND id < ?",
        (channel, threshold["id"]),
    )
    return int(cur.rowcount)


def prune_messages(
    *,
    max_age_days: int | None = None,
    keep_last_per_channel: int | None = None,
    path: Path | None = None,
) -> int:
    if max_age_days is None and keep_last_per_channel is None:
        raise ValueError("max_age_days or keep_last_per_channel must be provided")
    if max_age_days is not None and max_age_days < 0:
        raise ValueError("max_age_days must be >= 0")
    if keep_last_per_channel is not None and keep_last_per_channel < 1:
        raise ValueError("keep_last_per_channel must be >= 1")

    deleted = 0
    with _connect(path) as conn:
        if max_age_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
            cutoff_text = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
            cur = conn.execute("DELETE FROM messages WHERE created_at < ?", (cutoff_text,))
            deleted += int(cur.rowcount)
        if keep_last_per_channel is not None:
            channels = conn.execute("SELECT DISTINCT channel FROM messages").fetchall()
            for row in channels:
                deleted += _prune_channel(conn, row["channel"], keep_last_per_channel)
    return deleted
