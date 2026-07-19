# -*- coding: utf-8 -*-
"""Read/merge/save Claude Code and Codex statusline layouts.

Canonical segment metadata (label, description, default order/row) lives in
``global/statusline-segments.json``. The user's overrides (order, enabled, row)
are written to ``~/.claude/statusline-config.json``, which the deployed
``statusline.py`` reads at render time. Codex uses its native ``[tui]``
``status_line`` and ``status_line_use_colors`` keys in ``~/.codex/config.toml``.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from cabal._paths import CODEX_DIR, GLOBAL_DIR, TARGET

SEGMENTS_META_PATH: Path = GLOBAL_DIR / "statusline-segments.json"
USER_CONFIG_PATH: Path = TARGET / "statusline-config.json"
CODEX_SEGMENTS_META_PATH: Path = GLOBAL_DIR / "codex" / "statusline-segments.json"
CODEX_CONFIG_PATH: Path = CODEX_DIR / "config.toml"

CLAUDE_TARGET = "claude"
CODEX_TARGET = "codex"
_TUI_SECTION_RE = re.compile(r"^\s*\[tui\]\s*(?:#.*)?$")
_SECTION_RE = re.compile(r"^\s*\[")


def _read_segments(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    segs = data.get("segments")
    return segs if isinstance(segs, list) else []


def _meta_path(target: str) -> Path:
    return CODEX_SEGMENTS_META_PATH if target == CODEX_TARGET else SEGMENTS_META_PATH


def segment_meta(target: str = CLAUDE_TARGET) -> dict[str, dict[str, Any]]:
    """key → {label, group, description, row} from the canonical metadata file."""
    out: dict[str, dict[str, Any]] = {}
    for s in _read_segments(_meta_path(target)):
        key = s.get("key")
        if not key:
            continue
        out[key] = {
            "label": s.get("label", key),
            "group": s.get("group", ""),
            "description": s.get("description", ""),
            "row": int(s.get("row", 1)),
            "option": s.get("option"),
            "orderable": bool(s.get("orderable", True)),
        }
    return out


def _entry(
    key: str,
    enabled: bool,
    row: int,
    meta: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    item = meta.get(key, {})
    return {
        "key": key,
        "label": item.get("label", key),
        "group": item.get("group", ""),
        "description": item.get("description", ""),
        "enabled": enabled,
        "row": row,
        "option": item.get("option"),
        "orderable": item.get("orderable", True),
    }


def _read_codex_tui() -> dict[str, Any]:
    try:
        data = tomllib.loads(CODEX_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    tui = data.get("tui")
    return tui if isinstance(tui, dict) else {}


def _load_codex_layout() -> list[dict[str, Any]]:
    meta_segments = _read_segments(CODEX_SEGMENTS_META_PATH)
    meta = segment_meta(CODEX_TARGET)
    tui = _read_codex_tui()
    configured = tui.get("status_line")
    configured_items = (
        [key for key in configured if isinstance(key, str) and key in meta]
        if isinstance(configured, list)
        else None
    )
    use_colors = tui.get("status_line_use_colors", True)

    by_key = {s.get("key"): s for s in meta_segments if s.get("key")}
    ordered_keys: list[str]
    if configured_items is None:
        ordered_keys = list(by_key)
    else:
        seen = set(configured_items)
        ordered_keys = configured_items + [key for key in by_key if key not in seen]

    layout: list[dict[str, Any]] = []
    for key in ordered_keys:
        source = by_key[key]
        if source.get("option") == "status_line_use_colors":
            enabled = bool(use_colors)
        elif configured_items is None:
            enabled = bool(source.get("enabled", False))
        else:
            enabled = key in configured_items
        layout.append(_entry(key, enabled, 1, meta))
    return layout


def load_layout(target: str = CLAUDE_TARGET) -> list[dict[str, Any]]:
    """Ordered segments with metadata + current enabled/row.

    Starts from the canonical order; if a user config exists it reorders to match
    it and applies its enabled/row overrides. Segments present in the metadata but
    missing from the user config are appended (so newly-added segments surface).
    """
    if target == CODEX_TARGET:
        return _load_codex_layout()

    meta_segments = _read_segments(SEGMENTS_META_PATH)
    meta = segment_meta(CLAUDE_TARGET)
    user = _read_segments(USER_CONFIG_PATH)

    if not user:
        return [
            _entry(s["key"], bool(s.get("enabled", True)), int(s.get("row", 1)), meta)
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
            _entry(
                key,
                bool(s.get("enabled", True)),
                int(s.get("row", meta[key]["row"])),
                meta,
            )
        )
    for s in meta_segments:
        key = s.get("key")
        if key and key not in seen:
            ordered.append(
                _entry(key, bool(s.get("enabled", True)), int(s.get("row", 1)), meta)
            )
    return ordered


def _without_tui_keys(lines: list[str]) -> list[str]:
    keys = {"status_line", "status_line_use_colors"}
    out: list[str] = []
    index = 0
    while index < len(lines):
        match = re.match(r"^\s*([A-Za-z0-9_-]+)\s*=", lines[index])
        if not match or match.group(1) not in keys:
            out.append(lines[index])
            index += 1
            continue
        depth = lines[index].count("[") - lines[index].count("]")
        index += 1
        while depth > 0 and index < len(lines):
            depth += lines[index].count("[") - lines[index].count("]")
            index += 1
    return out


def _render_codex_config(
    text: str,
    status_line: list[str] | None,
    use_colors: bool | None,
) -> str:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if _TUI_SECTION_RE.match(line)), None)
    if start is None:
        if status_line is None and use_colors is None:
            return text
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[tui]")
        start = len(lines) - 1
        end = len(lines)
    else:
        end = next(
            (i for i in range(start + 1, len(lines)) if _SECTION_RE.match(lines[i])),
            len(lines),
        )

    body = _without_tui_keys(lines[start + 1 : end])
    managed: list[str] = []
    if status_line is not None:
        managed.append(f"status_line = {json.dumps(status_line)}")
    if use_colors is not None:
        managed.append(f"status_line_use_colors = {'true' if use_colors else 'false'}")
    updated = lines[: start + 1] + managed + body + lines[end:]
    rendered = "\n".join(updated).rstrip() + "\n"
    tomllib.loads(rendered)
    return rendered


def _save_codex_layout(layout: list[dict[str, Any]]) -> Path:
    status_line = [
        s["key"] for s in layout if s.get("enabled") and not s.get("option")
    ]
    colors = next(
        (
            bool(s.get("enabled"))
            for s in layout
            if s.get("option") == "status_line_use_colors"
        ),
        True,
    )
    CODEX_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = CODEX_CONFIG_PATH.read_text(encoding="utf-8") if CODEX_CONFIG_PATH.exists() else ""
    rendered = _render_codex_config(text, status_line, colors)
    temp_path = CODEX_CONFIG_PATH.with_suffix(".toml.tmp")
    temp_path.write_text(rendered, encoding="utf-8")
    temp_path.replace(CODEX_CONFIG_PATH)
    return CODEX_CONFIG_PATH


def save_layout(
    layout: list[dict[str, Any]], target: str = CLAUDE_TARGET
) -> Path:
    """Persist order/enabled/row to the user config file. Returns the path."""
    if target == CODEX_TARGET:
        return _save_codex_layout(layout)
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


def reset_layout(target: str = CLAUDE_TARGET) -> list[dict[str, Any]]:
    """Restore the selected target's repository defaults."""
    if target == CODEX_TARGET:
        meta = segment_meta(CODEX_TARGET)
        defaults = [
            _entry(
                s["key"],
                bool(s.get("enabled", False)),
                1,
                meta,
            )
            for s in _read_segments(CODEX_SEGMENTS_META_PATH)
            if s.get("key")
        ]
        _save_codex_layout(defaults)
        return defaults
    USER_CONFIG_PATH.unlink(missing_ok=True)
    return load_layout()
