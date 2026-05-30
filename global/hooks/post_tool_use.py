#!/usr/bin/env python3
"""PostToolUse hook — increments per-session tool / agent counters.

Writes `{session_id, agent_count, tool_count}` to ~/.claude/.session_state.json.
The statusline reads this file to render the activity counters segment.
Resets counters when the session_id changes. Never fails the session: any
error exits 0 silently.
"""
import json
import sys
from pathlib import Path

STATE_FILE = Path.home() / ".claude" / ".session_state.json"


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    session_id = data.get("session_id")
    tool_name = data.get("tool_name")
    if not session_id or not tool_name:
        return

    state = {"session_id": session_id, "agent_count": 0, "tool_count": 0}
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open(encoding="utf-8") as f:
                prev = json.load(f)
            if prev.get("session_id") == session_id:
                state["agent_count"] = int(prev.get("agent_count", 0))
                state["tool_count"] = int(prev.get("tool_count", 0))
        except Exception:
            pass

    state["tool_count"] += 1
    if tool_name == "Agent":
        state["agent_count"] += 1

    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
