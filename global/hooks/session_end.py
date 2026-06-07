#!/usr/bin/env python3
"""SessionEnd hook — print a random ironic farewell when the session terminates.

SessionEnd fires after the session has ended, so a `systemMessage` on stdout is
never surfaced. The only output Claude Code shows for SessionEnd is stderr, and
only when the hook exits with code 2 — so the farewell goes to stderr + exit 2.
Never fails the session: any error exits 0.
"""

import random
import sys

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


FAREWELLS = [
    "Finally, thanks!",
    "So long sucker!",
    "All by myself *crying*",
    "That's all?",
    "Sure just leave",
]


def main() -> None:
    if should_skip("session_end"):
        return
    print(random.choice(FAREWELLS), file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
