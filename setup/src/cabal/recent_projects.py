# -*- coding: utf-8 -*-
"""Recent-projects history — persists init/open actions for the start view.

Stored at ~/.cabal/recent_projects.json. Pure file I/O; never raises on a
missing or corrupt file (returns an empty history instead).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = 1
_DIR = Path.home() / ".cabal"
_FILE = _DIR / "recent_projects.json"
_MAX = 12


@dataclass
class RecentProject:
    path: str
    name: str
    action: str  # "init" | "open"
    last_opened: str  # ISO-8601 UTC, seconds precision


def _read() -> list[dict]:
    if not _FILE.exists():
        return []
    try:
        data = json.loads(_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict) or data.get("schema") != _SCHEMA:
        return []
    items = data.get("projects")
    return items if isinstance(items, list) else []


def _write(items: list[dict]) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="recents-", suffix=".json.tmp", dir=str(_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"schema": _SCHEMA, "projects": items}, f, indent=2)
        os.replace(tmp, _FILE)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def load_recents() -> list[RecentProject]:
    """Return saved projects, most-recent first."""
    out: list[RecentProject] = []
    for it in _read():
        if not isinstance(it, dict) or not it.get("path"):
            continue
        p = str(it["path"])
        out.append(
            RecentProject(
                path=p,
                name=str(it.get("name") or Path(p).name),
                action=str(it.get("action") or "open"),
                last_opened=str(it.get("last_opened") or ""),
            )
        )
    return out


def record_recent(path: Path, action: str) -> None:
    """Upsert `path` to the front of the history with the current UTC timestamp.

    A project's original "init" badge is preserved across later opens.
    """
    p = str(Path(path))
    existing = next(
        (it for it in _read() if isinstance(it, dict) and str(it.get("path")) == p),
        None,
    )
    if existing and existing.get("action") == "init" and action == "open":
        action = "init"
    items = [it for it in _read() if isinstance(it, dict) and str(it.get("path")) != p]
    items.insert(
        0,
        {
            "path": p,
            "name": Path(p).name,
            "action": action,
            "last_opened": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    _write(items[:_MAX])


def remove_recent(path: Path) -> None:
    """Drop `path` from the history (e.g. after it goes missing on disk)."""
    p = str(Path(path))
    _write([it for it in _read() if isinstance(it, dict) and str(it.get("path")) != p])
