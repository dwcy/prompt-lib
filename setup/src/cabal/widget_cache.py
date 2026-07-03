# -*- coding: utf-8 -*-
"""Stale-while-revalidate cache for home-screen widgets.

Single JSON file at ~/.cabal/cache.json with per-key payloads. Widgets read the
cached payload on mount for instant first paint, then revalidate in a worker.
Tests and sandboxed runs may override the directory with CABAL_CACHE_DIR.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_SCHEMA = 1
_CACHE_DIR = Path(os.environ.get("CABAL_CACHE_DIR", Path.home() / ".cabal"))
_CACHE_FILE = _CACHE_DIR / "cache.json"
_LOCK = threading.Lock()


def _read_all() -> dict[str, Any]:
    if not _CACHE_FILE.exists():
        return {"schema": _SCHEMA, "entries": {}}
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema": _SCHEMA, "entries": {}}
    if not isinstance(data, dict) or data.get("schema") != _SCHEMA:
        return {"schema": _SCHEMA, "entries": {}}
    entries = data.get("entries")
    if not isinstance(entries, dict):
        return {"schema": _SCHEMA, "entries": {}}
    return data


def _write_all(data: dict[str, Any]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="cache-", suffix=".json.tmp", dir=str(_CACHE_DIR))
    except OSError:
        return
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True, default=str)
        os.replace(tmp, _CACHE_FILE)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def load_entry(key: str) -> Any | None:
    """Return the cached payload for `key`, or None if absent / unreadable."""
    with _LOCK:
        data = _read_all()
    entry = data["entries"].get(key)
    if not isinstance(entry, dict):
        return None
    return entry.get("payload")


def load_entry_if_fresh(key: str, max_age: timedelta) -> Any | None:
    """Return the cached payload for `key` only if it was saved within `max_age`.

    Callers that need daily-refresh semantics (e.g. a slow network lookup) use
    this instead of `load_entry` so a stale entry falls through to a re-fetch.
    """
    with _LOCK:
        data = _read_all()
    entry = data["entries"].get(key)
    if not isinstance(entry, dict):
        return None
    ts_raw = entry.get("ts")
    if not isinstance(ts_raw, str):
        return None
    try:
        ts = datetime.fromisoformat(ts_raw)
    except ValueError:
        return None
    if datetime.now(timezone.utc) - ts > max_age:
        return None
    return entry.get("payload")


def save_entry(key: str, payload: Any) -> None:
    """Atomically persist `payload` under `key` with a UTC timestamp."""
    with _LOCK:
        data = _read_all()
        data["entries"][key] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        _write_all(data)
