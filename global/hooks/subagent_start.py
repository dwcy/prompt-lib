#!/usr/bin/env python3
"""PreToolUse(Task|Agent) hook — record the subagent being dispatched.

Writes ~/.claude/.subagent_state.json (name + model + start time) so the
statusline can show a "subagent running" chip, and prints a one-line chat
notice. Cleared by subagent_stop.py on SubagentStop.

We hook PreToolUse(Task|Agent) rather than SubagentStart because the model is
only present here (tool_input.model); the SubagentStart payload has no model
field. The dispatch tool is named Agent in current Claude Code, Task in older
versions — both are accepted. The start marker (started_at) is also the anchor
a future token-report step would use to attribute the subagent's transcript
slice. Never blocks: any error or non-dispatch call exits 0 (allow).
"""

import json
import sys
import time
from pathlib import Path

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


STATE_FILE = Path.home() / ".claude" / ".subagent_state.json"

# Mirrors pretool_task_isolation.py — keep the two lists in sync.
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
    if should_skip("subagent_start"):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") not in ("Task", "Agent"):
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    name = tool_input.get("subagent_type") or "subagent"
    model = tool_input.get("model")

    # If pretool_task_isolation will block this dispatch, don't record a running
    # chip — no SubagentStop fires to clear it, leaving a stale statusline entry.
    if (
        tool_input.get("subagent_type") not in READ_ONLY_SUBAGENTS
        and tool_input.get("run_in_background") is True
        and tool_input.get("isolation") != "worktree"
    ):
        sys.exit(0)

    state = {
        "running": True,
        "name": name,
        "model": model,
        "started_at": time.time(),
        "session_id": data.get("session_id"),
    }
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass

    suffix = f" · {model}" if model else ""
    print(json.dumps({"systemMessage": f"▶ subagent running: {name}{suffix}"}))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
