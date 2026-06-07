#!/usr/bin/env python3
"""SubagentStop hook — clear the running-subagent state and announce completion.

Reads ~/.claude/.subagent_state.json (written by subagent_start.py) for the
subagent name, clears it, and prints a one-line chat notice with the measured
number of tokens the subagent generated (summed from its transcript).

Cost in USD is NOT shown: it is not exposed to hooks (only the statusLine gets
cost, as a session total) and deriving it would require a hand-maintained,
drift-prone per-model rate table. Token count is measured from the transcript,
not estimated; if the transcript can't be read it is simply omitted. Never
fails the session: any error exits 0.
"""

import json
import sys
from pathlib import Path

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


STATE_FILE = Path.home() / ".claude" / ".subagent_state.json"


def _generated_tokens(transcript_path: str | None) -> int:
    """Sum output_tokens across the subagent's transcript. 0 if unreadable."""
    if not transcript_path:
        return 0
    p = Path(transcript_path)
    if not p.exists():
        return 0
    total = 0
    try:
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                usage = (
                    (obj.get("message") or {}).get("usage") or obj.get("usage") or {}
                )
                out = usage.get("output_tokens")
                if isinstance(out, int):
                    total += out
    except OSError:
        return 0
    return total


def main() -> None:
    if should_skip("subagent_stop"):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}

    name = None
    if STATE_FILE.exists():
        try:
            name = json.loads(STATE_FILE.read_text(encoding="utf-8")).get("name")
        except (json.JSONDecodeError, OSError):
            name = None
        try:
            STATE_FILE.unlink()
        except OSError:
            pass

    name = name or data.get("agent_type") or "subagent"
    tokens = _generated_tokens(data.get("transcript_path"))
    suffix = f" · {tokens:,} tokens generated" if tokens else ""
    print(json.dumps({"systemMessage": f"✓ subagent done: {name}{suffix}"}))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
