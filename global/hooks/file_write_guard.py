#!/usr/bin/env python3
"""
PreToolUse guard: blocks writes to the two security-critical hook files.
Prevents prompt injection from disabling the command guard or this guard itself.

Exit 0 → allow
Exit 2 → block
"""

import json
import sys
import os

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


# Only the security scripts themselves are protected — everything else in .claude/ is freely editable.
_HOOKS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
PROTECTED = {
    os.path.normpath(os.path.join(_HOOKS_DIR, "command_guard.py")),
    os.path.normpath(os.path.join(_HOOKS_DIR, "file_write_guard.py")),
}


def main():
    if should_skip("file_write_guard"):
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

    if os.path.normpath(file_path) in PROTECTED:
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": (
                        f"[Write Guard] Blocked write to protected security file: {file_path}\n\n"
                        "This file is a PreToolUse security hook. Overwriting it could disable "
                        "prompt-injection protection. If this edit is intentional, confirm with "
                        "the user before proceeding."
                    ),
                }
            )
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
