# -*- coding: utf-8 -*-
"""Agent eval & regression harness: pinned tasks x config profiles x N repetitions in throwaway
worktrees, scored by deterministic checks, transcript metrics, and a pairwise LLM judge.

Design tree: `specs/019-agent-eval-harness/`. Eval definitions live under `evals/` at repo root;
results are gitignored. Configuration isolation is per-run via a relocated `CLAUDE_CONFIG_DIR`.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
