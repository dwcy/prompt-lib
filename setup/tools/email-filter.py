# -*- coding: utf-8 -*-
"""Git smudge/clean filter that keeps personal identity out of commits.

Files matched by the `inject-email` filter in .gitattributes are committed
with placeholders; the working tree gets the real values on checkout:

    {{LOGGED_IN_EMAIL}}  ~/.claude.json oauthAccount.emailAddress
    {{GIT_USER_NAME}}    ~/.claude/identity/git-original.json, falling back
                         to `git config --global user.name`
    {{REPO_URL}}         `git config --get remote.origin.url`, normalised to
                         the https form without a trailing .git

A placeholder whose real value cannot be resolved is left as-is (safe
default). `clean` reverses every resolved substitution so real values can
never reach the index.

One-time per clone:
    git config filter.inject-email.smudge "python setup/tools/email-filter.py smudge"
    git config filter.inject-email.clean  "python setup/tools/email-filter.py clean"
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

EMAIL_PLACEHOLDER = "{{LOGGED_IN_EMAIL}}"
NAME_PLACEHOLDER = "{{GIT_USER_NAME}}"
REPO_PLACEHOLDER = "{{REPO_URL}}"


def logged_in_email() -> str | None:
    claude_json = Path.home() / ".claude.json"
    try:
        data = json.loads(claude_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    email = data.get("oauthAccount", {}).get("emailAddress")
    return email if isinstance(email, str) and email else None


def git_user_name() -> str | None:
    snapshot = Path.home() / ".claude" / "identity" / "git-original.json"
    try:
        name = json.loads(snapshot.read_text(encoding="utf-8")).get("name")
        if isinstance(name, str) and name:
            return name
    except (OSError, json.JSONDecodeError):
        pass
    try:
        r = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    name = r.stdout.strip()
    return name if r.returncode == 0 and name else None


def repo_url() -> str | None:
    try:
        r = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    url = r.stdout.strip()
    if r.returncode != 0 or not url:
        return None
    m = re.match(r"^git@([^:]+):(.+?)(?:\.git)?$", url)
    if m:
        return f"https://{m.group(1)}/{m.group(2)}"
    return url.removesuffix(".git")


def substitutions() -> dict[str, str]:
    pairs = {
        EMAIL_PLACEHOLDER: logged_in_email(),
        NAME_PLACEHOLDER: git_user_name(),
        REPO_PLACEHOLDER: repo_url(),
    }
    return {ph: val for ph, val in pairs.items() if val}


def smudge(text: str) -> str:
    for placeholder, value in substitutions().items():
        text = text.replace(placeholder, value)
    return text


def clean(text: str) -> str:
    for placeholder, value in substitutions().items():
        text = text.replace(value, placeholder)
    return text


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
