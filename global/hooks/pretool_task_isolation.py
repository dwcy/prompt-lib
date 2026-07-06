#!/usr/bin/env python3
"""PreToolUse guard for the subagent-dispatch tool (named Agent in current
Claude Code, Task in older versions): block concurrent background writers
that don't opt into worktree isolation.

Enforces the rule documented in docs/parallel-isolation.md:
  - Read-only subagents are exempt (allowlist below).
  - Foreground (run_in_background != true) dispatch is exempt (V1 gap).
  - Background dispatch with isolation: "worktree" is allowed.
  - Otherwise → block.

Exit 0 → allow. Exit 2 → block (JSON reason on stdout).
"""

import json
import sys

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


READ_ONLY_SUBAGENTS = {
    "Explore",
    "Plan",
    "claude-code-guide",
    "statusline-setup",
    "code-plan-verifier",
    "gitignore-auditor",
    "github-config-manager",
    "load-project",
    "secret-auditor",
}


def main() -> None:
    if should_skip("pretool_task_isolation"):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") not in ("Task", "Agent"):
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    subagent_type = tool_input.get("subagent_type")
    run_in_background = tool_input.get("run_in_background") is True
    isolation = tool_input.get("isolation")

    if subagent_type in READ_ONLY_SUBAGENTS:
        sys.exit(0)
    if not run_in_background:
        sys.exit(0)
    if isolation == "worktree":
        sys.exit(0)

    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    "[Parallel Isolation] Concurrent background writing subagent "
                    f'(`{subagent_type}`) dispatched without `isolation: "worktree"`.\n\n'
                    "Without isolation, two writers on the same working tree silently "
                    "overwrite each other's edits. Either:\n"
                    '  - add `isolation: "worktree"` to this Agent/Task call, or\n'
                    "  - change the dispatch to sequential (no `run_in_background: true`).\n\n"
                    "See docs/parallel-isolation.md for the rule and the read-only "
                    "agent allowlist."
                ),
            }
        )
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
