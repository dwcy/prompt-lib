#!/usr/bin/env python3
"""SessionEnd hook — print a random ironic farewell when the session terminates.

Emits JSON with `systemMessage` so Claude Code displays it in the UI.
Never fails the session: any error exits 0.
"""
import json
import random
import sys


FAREWELLS = [
    "Finally, thanks!",
    "So long sucker!",
    "All by myself *crying*",
    "That's all?",
    "Sure just leave",
]


def main() -> None:
    print(json.dumps({"systemMessage": random.choice(FAREWELLS)}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
