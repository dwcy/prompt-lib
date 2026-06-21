# -*- coding: utf-8 -*-
"""Catalog of toggleable Claude Code boolean settings + global/local read-merge.

The Claude Settings screen shows these with the global settings as the baseline;
toggling any one writes its value into the active project's
.claude/settings.local.json, which overrides the global default at runtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cabal._paths import GLOBAL_DIR, TARGET


@dataclass(frozen=True)
class SettingDef:
    key: str
    label: str
    description: str
    default: bool


CATALOG: list[SettingDef] = [
    SettingDef(
        "remoteControlAtStartup",
        "Remote Control at startup",
        "Connect Remote Control automatically so every session is steerable from claude.ai/code or the Claude mobile app.",
        False,
    ),
    SettingDef(
        "verbose",
        "Verbose output",
        "Show full command output and expanded tool detail in the transcript.",
        False,
    ),
    SettingDef(
        "autoCompactEnabled",
        "Auto-compact",
        "Automatically compact the conversation when context approaches the limit.",
        True,
    ),
    SettingDef(
        "autoMemoryEnabled",
        "Auto memory",
        "Read from and write to the auto-memory directory across sessions.",
        True,
    ),
    SettingDef(
        "awaySummaryEnabled",
        "Away summary",
        "Show a one-line session recap when you return after time away.",
        True,
    ),
    SettingDef(
        "fileCheckpointingEnabled",
        "File checkpointing",
        "Snapshot files before each edit so /rewind can restore them.",
        True,
    ),
    SettingDef(
        "includeGitInstructions",
        "Git instructions",
        "Include the built-in commit and PR workflow guidance in the system prompt.",
        True,
    ),
    SettingDef(
        "respectGitignore",
        "Respect .gitignore",
        "Make the @ file picker honour .gitignore patterns.",
        True,
    ),
    SettingDef(
        "alwaysThinkingEnabled",
        "Always thinking",
        "Enable extended thinking by default for all sessions.",
        False,
    ),
    SettingDef(
        "enableAllProjectMcpServers",
        "Auto-approve project MCP",
        "Automatically approve all MCP servers declared in project .mcp.json files.",
        False,
    ),
    SettingDef(
        "agentPushNotifEnabled",
        "Agent push notifications",
        "Let Claude send proactive push notifications to your phone.",
        False,
    ),
    SettingDef(
        "disableAllHooks",
        "Disable all hooks",
        "Turn off all hooks and the custom status line.",
        False,
    ),
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def global_settings_path() -> Path:
    """Deployed ~/.claude/settings.json if present, else the repo source."""
    deployed = TARGET / "settings.json"
    return deployed if deployed.exists() else GLOBAL_DIR / "settings.json"


def local_settings_path(project: Path) -> Path:
    return project / ".claude" / "settings.local.json"


def read_global() -> dict[str, Any]:
    return _read_json(global_settings_path())


def read_local(project: Path) -> dict[str, Any]:
    return _read_json(local_settings_path(project))


def global_value(sd: SettingDef, gl: dict[str, Any]) -> bool:
    return bool(gl.get(sd.key, sd.default))


def effective_value(sd: SettingDef, gl: dict[str, Any], lo: dict[str, Any]) -> bool:
    if sd.key in lo:
        return bool(lo[sd.key])
    return global_value(sd, gl)


def write_local(project: Path, key: str, value: bool) -> Path:
    """Merge a single key into settings.local.json, preserving other keys."""
    target = local_settings_path(project)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _read_json(target)
    data[key] = value
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return target


def reset_local(project: Path) -> int:
    """Drop every catalog key from settings.local.json. Returns the count removed."""
    target = local_settings_path(project)
    data = _read_json(target)
    removed = [sd.key for sd in CATALOG if sd.key in data]
    for key in removed:
        del data[key]
    if removed:
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return len(removed)
