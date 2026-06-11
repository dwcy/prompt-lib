#!/usr/bin/env python3
"""PreToolUse guard: blocks Write/Edit when the target repo is on a refused branch.

Enforces the "branch before starting work" rule. If the file being edited lives in a
git repo currently on a branch listed in git-policy.json `refuse_on_branches`
(default main/master), the edit is blocked until a feature branch exists — branching
is a pre-work step, not a commit-time one. Fail-open: anything we cannot positively
resolve (no repo, git missing, unreadable policy, detached HEAD) is allowed.

Exit 0 -> allow
Exit 2 -> block
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


_DEFAULT_REFUSED = ("main", "master")
_POLICY_PATHS = (
    Path.home() / ".claude" / "git-policy.json",
    Path.home() / ".claude" / "git" / "git-policy.default.json",
)


def _refused_branches() -> set[str]:
    for policy in _POLICY_PATHS:
        try:
            data = json.loads(policy.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        branches = data.get("refuse_on_branches")
        if isinstance(branches, list) and branches:
            return {str(b) for b in branches}
    return set(_DEFAULT_REFUSED)


def _nearest_existing_dir(file_path: str) -> Path | None:
    target = Path(file_path).expanduser()
    start = target if target.is_dir() else target.parent
    while not start.exists() and start != start.parent:
        start = start.parent
    return start if start.exists() else None


def _current_branch(file_path: str) -> str | None:
    start = _nearest_existing_dir(file_path)
    if start is None:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def main() -> None:
    if should_skip("pretool_branch_guard"):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") not in ("Write", "Edit"):
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    branch = _current_branch(file_path)
    if branch is None or branch not in _refused_branches():
        sys.exit(0)

    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    f"[Branch Guard] You are on '{branch}', a protected branch. "
                    "Create a feature branch BEFORE editing — this is a pre-work step, "
                    "not part of committing:\n"
                    "  git -C <repo> checkout -b <type>/<slug>\n"
                    "then retry the edit. Uncommitted changes follow the checkout. "
                    "To bypass for this session, set "
                    "PROMPTLIB_DISABLED_HOOKS=pretool_branch_guard."
                ),
            }
        )
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
