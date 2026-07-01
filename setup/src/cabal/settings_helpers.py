# -*- coding: utf-8 -*-
"""Pure helpers for processing repo `settings.json` before deploy.

Claude Code does NOT read MCP server definitions from settings.json — those
blocks are silently ignored. The canonical interface is `claude mcp add`
which writes to `~/.claude.json`. Stripping these fields here keeps the
deployed file honest. See `global/skills/add-mcp/SKILL.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

from cabal._paths import GLOBAL_DIR
from cabal.os_filters import translate_for_os


def _effective_settings_text(src: Path) -> str:
    """Return settings.json content stripped of dead `mcpServers` / `mcpServersDisabled`,
    with OS-specific tokens translated for the deploy target.

    Why: Claude Code does NOT read MCP server definitions from settings.json — those
    blocks are silently ignored. The canonical interface is `claude mcp add` which
    writes to `~/.claude.json`. Stripping these fields keeps the deployed file honest
    so future readers don't think the config is active. See global/skills/add-mcp/SKILL.md.
    Additionally, the repo authors paths with $USERPROFILE (Windows) — on POSIX
    shells we swap to $HOME via translate_for_os so hook commands resolve.
    """
    data = json.loads(src.read_text(encoding="utf-8"))
    data.pop("mcpServers", None)
    data.pop("mcpServersDisabled", None)
    text = json.dumps(data, indent=2) + "\n"
    return translate_for_os(src.name, text)


def _is_settings_json(src_file: Path) -> bool:
    return src_file.name == "settings.json" and src_file.parent == GLOBAL_DIR
