# -*- coding: utf-8 -*-
"""Git smudge/clean filter that keeps the logged-in email out of commits.

Files matched by the `inject-email` filter in .gitattributes are committed
with the {{LOGGED_IN_EMAIL}} placeholder; the working tree gets the real
address from ~/.claude.json (oauthAccount.emailAddress) on checkout.

One-time per clone:
    git config filter.inject-email.smudge "python setup/tools/email-filter.py smudge"
    git config filter.inject-email.clean  "python setup/tools/email-filter.py clean"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PLACEHOLDER = "{{LOGGED_IN_EMAIL}}"


def logged_in_email() -> str | None:
    claude_json = Path.home() / ".claude.json"
    try:
        data = json.loads(claude_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    email = data.get("oauthAccount", {}).get("emailAddress")
    return email if isinstance(email, str) and email else None


def smudge(text: str) -> str:
    email = logged_in_email()
    return text.replace(PLACEHOLDER, email) if email else text


def clean(text: str) -> str:
    email = logged_in_email()
    return text.replace(email, PLACEHOLDER) if email else text


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("smudge", "clean"):
        print("usage: email-filter.py smudge|clean", file=sys.stderr)
        return 2
    text = sys.stdin.buffer.read().decode("utf-8")
    out = smudge(text) if sys.argv[1] == "smudge" else clean(text)
    sys.stdout.buffer.write(out.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
