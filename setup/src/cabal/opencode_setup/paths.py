# -*- coding: utf-8 -*-
"""Path constants for OpenCode setup."""

from __future__ import annotations

from pathlib import Path

from cabal._paths import GLOBAL_DIR

OPENCODE_SOURCE_DIR: Path = GLOBAL_DIR / "opencode"
OPENCODE_TARGET: Path = Path.home() / ".config" / "opencode"
