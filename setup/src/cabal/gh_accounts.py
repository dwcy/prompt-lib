# -*- coding: utf-8 -*-
"""GitHub CLI multi-account service — list / switch / add / forget accounts.

gh >= 2.40 supports multiple accounts per host; the active one is toggled with
`gh auth switch`. `gh auth status` has no JSON output, so we parse its text
form; it can also exit non-zero when any account has an invalid token, so
output is parsed regardless of return code.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass

_HOST = "github.com"
_TIMEOUT = 15

_ACCOUNT_RE = re.compile(
    r"(?P<state>Logged in to|Failed to log in to)\s+(?P<host>\S+)\s+account\s+"
    r"(?P<user>\S+?)(?:\s+\((?P<storage>[^)]*)\))?\s*$"
)
_ACTIVE_RE = re.compile(r"Active account:\s*(?P<active>true|false)", re.IGNORECASE)


@dataclass(frozen=True)
class GhAccount:
    user: str
    host: str
    active: bool
    valid: bool
    storage: str


def parse_auth_status(text: str) -> list[GhAccount]:
    accounts: list[GhAccount] = []
    cur: dict | None = None

    def flush() -> None:
        nonlocal cur
        if cur is not None:
            accounts.append(GhAccount(**cur))
            cur = None

    for line in text.splitlines():
        m = _ACCOUNT_RE.search(line)
        if m:
            flush()
            cur = {
                "user": m["user"],
                "host": m["host"],
                "active": False,
                "valid": m["state"] == "Logged in to",
                "storage": m["storage"] or "",
            }
            continue
        if cur is not None:
            a = _ACTIVE_RE.search(line)
            if a:
                cur["active"] = a["active"].lower() == "true"
    flush()
    return accounts


def _run_gh(args: list[str], stdin: str | None = None) -> tuple[int, str]:
    """Run gh and return (returncode, combined output). -1 on launch failure."""
    if not shutil.which("gh"):
        return -1, "gh CLI not found — install GitHub CLI first"
    try:
        r = subprocess.run(
            ["gh", *args],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)
    return r.returncode, "\n".join(p for p in (r.stdout.strip(), r.stderr.strip()) if p)


def list_accounts(host: str = _HOST) -> list[GhAccount]:
    _, out = _run_gh(["auth", "status", "--hostname", host])
    return parse_auth_status(out)


def switch_account(user: str, host: str = _HOST) -> tuple[bool, str]:
    code, out = _run_gh(["auth", "switch", "--hostname", host, "--user", user])
    return code == 0, out or f"switched to {user}"


def add_account_with_token(token: str, host: str = _HOST) -> tuple[bool, str]:
    """Register a token as an additional gh account (`gh auth login --with-token`)."""
    code, out = _run_gh(
        ["auth", "login", "--hostname", host, "--with-token"], stdin=token
    )
    return code == 0, out or "account added"


def forget_account(user: str, host: str = _HOST) -> tuple[bool, str]:
    code, out = _run_gh(["auth", "logout", "--hostname", host, "--user", user])
    return code == 0, out or f"removed {user}"
