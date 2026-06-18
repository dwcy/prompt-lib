# -*- coding: utf-8 -*-
"""Path constants for Codex setup."""

from __future__ import annotations

from pathlib import Path

from cabal._paths import GLOBAL_DIR

CODEX_SOURCE_DIR: Path = GLOBAL_DIR / "codex"
CODEX_TARGET: Path = Path.home() / ".codex"
CODEX_PROMPTLIB_TARGET: Path = CODEX_TARGET / "prompt-lib"
