# -*- coding: utf-8 -*-
"""Read/merge/save the statusline layout the wizard's Statusline screen edits.

Canonical segment metadata (label, description, default order/row) lives in
``global/statusline-segments.json``. The user's overrides (order, enabled, row)
are written to ``~/.claude/statusline-config.json``, which the deployed
``statusline.py`` reads at render time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cabal._paths import GLOBAL_DIR, TARGET

SEGMENTS_META_PATH: Path = GLOBAL_DIR / "statusline-segments.json"
USER_CONFIG_PATH: Path = TARGET / "statusline-config.json"


def _read_segments(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    segs = data.get("segments")
    return segs if isinstance(segs, list) else []


def segment_meta() -> dict[str, dict[str, Any]]:
    """key → {label, description, row} from the canonical metadata file."""
    out: dict[str, dict[str, Any]] = {}
    for s in _read_segments(SEGMENTS_META_PATH):
        key = s.get("key")
        if not key:
            continue
        out[key] = {
            "label": s.get("label", key),
            "description": s.get("description", ""),
            "row": int(s.get("row", 1)),
        }
    return out


def load_layout() -> list[dict[str, Any]]:
    """Ordered segments with metadata + current enabled/row.

    Starts from the canonical order; if a user config exists it reorders to match
    it and applies its enabled/row overrides. Segments present in the metadata but
    missing from the user config are appended (so newly-added segments surface).
    """
    meta_segments = _read_segments(SEGMENTS_META_PATH)
    meta = segment_meta()
    user = _read_segments(USER_CONFIG_PATH)

    def entry(key: str, enabled: bool, row: int) -> dict[str, Any]:
        m = meta.get(key, {})
        return {
            "key": key,
            "label": m.get("label", key),
            "description": m.get("description", ""),
            "enabled": enabled,
            "row": row,
        }

    if not user:
        return [
            entry(s["key"], bool(s.get("enabled", True)), int(s.get("row", 1)))
            for s in meta_segments
            if s.get("key")
        ]

    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for s in user:
        key = s.get("key")
        if not key or key not in meta or key in seen:
            continue
        seen.add(key)
        ordered.append(
            entry(
                key, bool(s.get("enabled", True)), int(s.get("row", meta[key]["row"]))
            )
        )
    for s in meta_segments:
        key = s.get("key")
        if key and key not in seen:
            ordered.append(
                entry(key, bool(s.get("enabled", True)), int(s.get("row", 1)))
            )
    return ordered


def save_layout(layout: list[dict[str, Any]]) -> Path:
    """Persist order/enabled/row to the user config file. Returns the path."""
    USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "$schema_version": 1,
        "segments": [
            {"key": s["key"], "enabled": bool(s["enabled"]), "row": int(s["row"])}
            for s in layout
        ],
    }
    USER_CONFIG_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return USER_CONFIG_PATH


def reset_layout() -> list[dict[str, Any]]:
    """Delete the user config so the canonical defaults apply again."""
    USER_CONFIG_PATH.unlink(missing_ok=True)
    return load_layout()
