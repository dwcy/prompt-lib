# -*- coding: utf-8 -*-
"""OS-conditional filename filters + per-OS file content translation."""

from __future__ import annotations

import platform
from pathlib import Path


def _os_should_skip(filename: str) -> bool:
    """Filename-prefix convention for OS-specific files.

    Names starting with linux_ / darwin_ / windows_ deploy only on the matching OS.
    Anything else deploys everywhere.
    """
    sys = platform.system()  # "Windows" | "Linux" | "Darwin"
    if filename.startswith("linux_") and sys != "Linux":
        return True
    if filename.startswith("darwin_") and sys != "Darwin":
        return True
    if filename.startswith("windows_") and sys != "Windows":
        return True
    return False


_PLUGIN_ONLY_FILES = frozenset({".mcp.json", "hooks/hooks.json"})


def _is_plugin_only(rel_path: Path) -> bool:
    """Skip files that Claude Code loads only when `global/` is installed as a plugin."""
    posix = rel_path.as_posix()
    if posix in _PLUGIN_ONLY_FILES:
        return True
    parts = rel_path.parts
    return bool(parts) and parts[0] == ".claude-plugin"


def translate_for_os(filename: str, text: str) -> str:
    """Rewrite OS-specific tokens in a config file before it is deployed.

    The repo's settings.json is authored Windows-canonical ($USERPROFILE). On
    POSIX shells that variable is empty, so hook/statusline command paths break.
    Swap it for $HOME, which resolves correctly on Linux, macOS, and git-bash.
    """
    if filename != "settings.json" or platform.system() == "Windows":
        return text
    return text.replace("$USERPROFILE", "$HOME")
