# -*- coding: utf-8 -*-
"""Read-only OpenCode setup status probes."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cabal.env_detect import _has_opencode_desktop
from cabal.opencode_setup.paths import OPENCODE_TARGET


@dataclass(frozen=True)
class OpenCodeStatus:
    cli: bool
    desktop_app: bool
    version: str | None
    global_config: bool
    tui_config: bool
    skills_dir: bool
    tools_dir: bool
    codex_cli: bool
    codex_mcp_configured: bool
    claude_cli: bool
    gemini_cli: bool
    antigravity_cli: bool

    @property
    def summary(self) -> str:
        version = f" ({self.version})" if self.version else ""
        return "installed" + version if self.cli else "not installed"

    @property
    def desktop_summary(self) -> str:
        return "installed" if self.desktop_app else "not detected"


def _version(command: str) -> str | None:
    resolved = shutil.which(command)
    if not resolved:
        return None
    try:
        result = subprocess.run(
            [resolved, "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    lines = (result.stdout or result.stderr).strip().splitlines()
    return lines[0] if lines else None


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def codex_mcp_configured(target: Path = OPENCODE_TARGET) -> bool:
    cfg = _load_json(target / "opencode.json")
    mcp = cfg.get("mcp")
    if not isinstance(mcp, dict):
        return False
    codex = mcp.get("codex")
    return isinstance(codex, dict) and codex.get("type") == "local"


def opencode_status(target: Path = OPENCODE_TARGET) -> OpenCodeStatus:
    return OpenCodeStatus(
        cli=shutil.which("opencode") is not None,
        desktop_app=_has_opencode_desktop(),
        version=_version("opencode"),
        global_config=(target / "opencode.json").is_file(),
        tui_config=(target / "tui.json").is_file(),
        skills_dir=(target / "skills").is_dir(),
        tools_dir=(target / "tools").is_dir(),
        codex_cli=shutil.which("codex") is not None,
        codex_mcp_configured=codex_mcp_configured(target),
        claude_cli=shutil.which("claude") is not None,
        gemini_cli=shutil.which("gemini") is not None,
        antigravity_cli=shutil.which("antigravity") is not None,
    )
