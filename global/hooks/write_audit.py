#!/usr/bin/env python3
"""
PostToolUse hook: appends Write and Edit operations to write_audit.jsonl.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AUDIT_FILE = Path.home() / ".claude" / "write_audit.jsonl"


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") not in ("Write", "Edit"):
        sys.exit(0)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": data.get("tool_name"),
        "path": data.get("tool_input", {}).get("file_path", ""),
    }

    try:
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Never block on audit failure

    sys.exit(0)


if __name__ == "__main__":
    main()
