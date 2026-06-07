#!/usr/bin/env python3
"""Background update checker — polls npm for the latest @anthropic-ai/claude-code
release and writes it to ~/.claude/.update_state.json. Rate-limited to one
network call per 6 hours. Fire-and-forget; never fails the caller.
"""

import json
import time
import urllib.request
from pathlib import Path

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


STATE_FILE = Path.home() / ".claude" / ".update_state.json"
TTL_SECONDS = 6 * 3600
NPM_URL = "https://registry.npmjs.org/@anthropic-ai/claude-code/latest"


def main() -> None:
    if should_skip("check_claude_update"):
        return
    now = int(time.time())
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open(encoding="utf-8") as f:
                state = json.load(f)
            if now - int(state.get("checked_at", 0)) < TTL_SECONDS:
                return
        except Exception:
            pass

    try:
        req = urllib.request.Request(NPM_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            payload = json.loads(resp.read())
    except Exception:
        return

    latest = payload.get("version")
    if not latest:
        return

    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump({"latest": latest, "checked_at": now}, f)
    except Exception:
        return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
