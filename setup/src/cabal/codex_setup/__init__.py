# -*- coding: utf-8 -*-
"""Codex setup feature package.

This package intentionally keeps Codex deploy/local-setup logic separate from
the existing Claude setup flow.
"""

from cabal.codex_setup.paths import CODEX_SOURCE_DIR, CODEX_TARGET

__all__ = ["CODEX_SOURCE_DIR", "CODEX_TARGET"]
