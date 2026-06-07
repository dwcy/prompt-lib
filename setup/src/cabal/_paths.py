# -*- coding: utf-8 -*-
"""Path resolution for the three run-modes (source / wheel / frozen exe).

Three install layouts are supported:
  - Source checkout: this file lives at <repo>/setup/src/cabal/_paths.py with
    resource roots at <repo>/global/ and <repo>/setup/env/.
  - PyPI wheel: data force-included under <site-packages>/cabal/_data/ at
    build time, mirroring the repo layout (global/, setup/env/, setup/mcp-templates.json).
  - Frozen exe (PyInstaller --onefile): resources extracted into sys._MEIPASS,
    same layout as the wheel _data/ tree.
"""

from __future__ import annotations

import sys
from pathlib import Path

IS_FROZEN = getattr(sys, "frozen", False)
IS_INSTALLED = False  # toggled in _resource_root() when the wheel data dir is found


def _resource_root() -> Path:
    """Directory containing bundled `global/` and `setup/` trees."""
    global IS_INSTALLED
    if IS_FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    pkg_data = Path(__file__).resolve().parent / "_data"
    if pkg_data.is_dir():
        IS_INSTALLED = True
        return pkg_data
    # source checkout: setup/src/cabal/_paths.py → repo root
    return Path(__file__).resolve().parents[3]


def _detect_repo_dir() -> Path | None:
    """Return the repo working tree if we're running from a source checkout; else None."""
    if IS_FROZEN:
        candidate = Path(sys.executable).resolve().parent
        for parent in (candidate, *candidate.parents):
            if (parent / ".git").exists():
                return parent
        return None
    repo_candidate = Path(__file__).resolve().parents[3]
    # `.git` is a directory in the primary checkout, a file in a linked worktree
    # (`gitdir: …`). Accept both so the updater works from worktrees too.
    if (repo_candidate / ".git").exists():
        return repo_candidate
    return None


SCRIPT_DIR = Path(__file__).resolve().parent
RESOURCE_ROOT = _resource_root()
REPO_DIR: Path | None = _detect_repo_dir()
GLOBAL_DIR = RESOURCE_ROOT / "global"
ENV_DIR = RESOURCE_ROOT / "setup" / "env"
ENV_FILE = ENV_DIR / "setup.env.example.json"
MCP_TEMPLATES_FILE = RESOURCE_ROOT / "setup" / "mcp-templates.json"
TARGET = Path.home() / ".claude"
