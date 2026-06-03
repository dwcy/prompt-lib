# -*- coding: utf-8 -*-
"""Load/save ~/.claude/git-policy.json — mirrors global/scripts/git-identity.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CLAUDE_DIR: Path = Path.home() / ".claude"
POLICY_PATH: Path = CLAUDE_DIR / "git-policy.json"
POLICY_DEFAULT_PATH: Path = CLAUDE_DIR / "git" / "git-policy.default.json"

BUILTIN_DEFAULTS: dict[str, Any] = {
    "agent_name": "Claude Agent",
    "agent_email": "my@agent.commit",
    "allowed_types": ["feat", "task", "fix", "refactor", "test", "docs"],
    "refuse_on_branches": ["main", "master"],
    "tags": {"agent_may_tag": False, "auto_push": False},
}


def load_policy() -> dict[str, Any]:
    """Return the effective policy. Lookup order: user file → seeded default → built-in."""
    for path in (POLICY_PATH, POLICY_DEFAULT_PATH):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    return json.loads(json.dumps(BUILTIN_DEFAULTS))


def save_policy(policy: dict[str, Any]) -> Path:
    """Write the user policy file. Returns the path written."""
    POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    POLICY_PATH.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    return POLICY_PATH


def policy_source() -> Path | str:
    """Return where the current effective policy is loaded from."""
    if POLICY_PATH.exists():
        return POLICY_PATH
    if POLICY_DEFAULT_PATH.exists():
        return POLICY_DEFAULT_PATH
    return "<built-in defaults>"
