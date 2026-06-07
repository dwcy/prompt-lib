#!/usr/bin/env python3
"""Runtime gate for prompt-lib hooks.

Lets the user silence hooks at runtime without editing settings.json or
restarting Claude Code:

  PROMPTLIB_HOOK_PROFILE=off          → disable every prompt-lib hook
  PROMPTLIB_DISABLED_HOOKS=a,b,c      → disable specific hooks by short name
                                        (filename without .py)

Each hook calls `should_skip("<name>")` at the top of main() and exits 0 when
it returns True. Imported as a sibling module — hooks run from
~/.claude/hooks/, which Python puts on sys.path[0], so `from _gate import
should_skip` resolves there.
"""

from __future__ import annotations

import os


def should_skip(hook_name: str) -> bool:
    if os.environ.get("PROMPTLIB_HOOK_PROFILE", "").strip().lower() == "off":
        return True
    disabled = os.environ.get("PROMPTLIB_DISABLED_HOOKS", "")
    return hook_name in {n.strip() for n in disabled.split(",") if n.strip()}
