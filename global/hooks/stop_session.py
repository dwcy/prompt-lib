#!/usr/bin/env python3
"""Stop hook — warn about uncommitted changes at session end.

Cross-platform (Windows / Linux / macOS). Emits JSON with `additionalContext`
when the working tree is dirty. Never fails the session: any error exits 0.
"""

import json
import subprocess
import sys

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def main() -> None:
    if should_skip("stop_session"):
        return
    if git("rev-parse", "--git-dir").returncode != 0:
        return

    status = git("status", "--porcelain").stdout
    lines = [ln for ln in status.splitlines() if ln.strip()]
    if not lines:
        return

    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "?"
    print(
        json.dumps(
            {
                "additionalContext": (
                    f"Session ending with {len(lines)} uncommitted change(s) on branch "
                    f"'{branch}'. Consider committing or stashing before closing."
                )
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
