# -*- coding: utf-8 -*-
"""Load/save ~/.claude/context-guard-policy.json — mirrors cabal.git_policy.

Opt-in config for the advisory /compact nudge (see global/hooks/context_guard.py and
the `context_guard` statusline segment). Absence of the file means the feature is off —
there is no secondary "default" file to fall back to, unlike git-policy.json, because
`enabled: False` is itself the correct behavior when nothing has ever been configured.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CLAUDE_DIR: Path = Path.home() / ".claude"
POLICY_PATH: Path = CLAUDE_DIR / "context-guard-policy.json"

BUILTIN_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "threshold_percent": 80,
    "max_context_tokens": 200000,
}


def load_policy() -> dict[str, Any]:
    """Return the effective policy: user file merged over built-in defaults."""
    if POLICY_PATH.exists():
        try:
            data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = dict(BUILTIN_DEFAULTS)
                merged.update(data)
                return merged
        except (OSError, json.JSONDecodeError):
            pass
    return dict(BUILTIN_DEFAULTS)


def save_policy(policy: dict[str, Any]) -> Path:
    """Write the user policy file. Returns the path written."""
    POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    POLICY_PATH.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    return POLICY_PATH


def policy_source() -> Path | str:
    """Return where the current effective policy is loaded from."""
    if POLICY_PATH.exists():
        return POLICY_PATH
    return "<built-in defaults — feature disabled>"
