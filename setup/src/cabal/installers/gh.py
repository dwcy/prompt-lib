# -*- coding: utf-8 -*-
"""GitHub CLI (gh) — install, version check, OAuth Device flow + token fetch."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from typing import Callable


def gh_status() -> str:
    if not shutil.which("gh"):
        return "not installed"
    r = subprocess.run(["gh", "--version"], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()[0] if r.returncode == 0 else ""
    return f"installed {v}" if v else "installed"


def gh_fetch_token() -> tuple[bool, str, str]:
    """Get GitHub token via gh CLI. Returns (success, token, message).

    Uses `gh auth token` as the primary check — if it returns a token the user
    is authenticated regardless of what `gh auth status` reports (status can
    return non-zero even when a valid token exists due to scope/keychain quirks).
    """
    if not shutil.which("gh"):
        return False, "", "gh CLI not found — install GitHub CLI first"
    token_r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    t = token_r.stdout.strip()
    if token_r.returncode == 0 and t:
        return True, t, "Token fetched from gh CLI"
    return False, "", "Not logged in — click Login with GitHub, authenticate, then click Fetch via gh."


# GitHub CLI's public client_id (visible in gh source: internal/authflow/flow.go).
# Device flow does not require a client secret. Override via env var if you've
# registered your own OAuth App.
_GITHUB_CLIENT_ID = os.environ.get("PROMPT_LIB_GH_CLIENT_ID", "178c6fc778ccc68e1d6a")


def gh_device_init(scopes: list[str]) -> dict | None:
    """Start OAuth Device Authorization Grant. Returns response dict or None on failure."""
    import urllib.parse, urllib.request
    body = urllib.parse.urlencode({
        "client_id": _GITHUB_CLIENT_ID,
        "scope": " ".join(scopes),
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://github.com/login/device/code",
        data=body,
        headers={"Accept": "application/json", "User-Agent": "prompt-lib-wizard"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def gh_device_poll(
    device_code: str,
    interval: int,
    deadline: float,
    cancelled: Callable[[], bool],
) -> tuple[bool, str, str]:
    """Poll for the access token until success, denial, expiry, cancel, or deadline.

    Returns (ok, token, message). `cancelled()` is checked between sleeps so the UI can abort.
    """
    import time, urllib.parse, urllib.request
    cur_interval = max(1, interval)
    while time.monotonic() < deadline:
        if cancelled():
            return False, "", "cancelled"
        time.sleep(cur_interval)
        if cancelled():
            return False, "", "cancelled"
        body = urllib.parse.urlencode({
            "client_id": _GITHUB_CLIENT_ID,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://github.com/login/oauth/access_token",
            data=body,
            headers={"Accept": "application/json", "User-Agent": "prompt-lib-wizard"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            return False, "", f"network error: {e}"
        if "access_token" in data:
            return True, data["access_token"], "authorized"
        err = data.get("error", "")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            cur_interval += 5
            continue
        if err == "expired_token":
            return False, "", "code expired — try again"
        if err == "access_denied":
            return False, "", "access denied"
        return False, "", f"oauth error: {err or 'unknown'}"
    return False, "", "timed out"


def gh_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            r = subprocess.run(["winget", "install", "--id", "GitHub.cli", "-e"], capture_output=True, text=True)
            return r.returncode == 0, "winget install GitHub.cli"
        if shutil.which("scoop"):
            r = subprocess.run(["scoop", "install", "gh"], capture_output=True, text=True)
            return r.returncode == 0, "scoop install gh"
        return False, "Install manually from https://cli.github.com"
    if sysname == "Darwin":
        if shutil.which("brew"):
            r = subprocess.run(["brew", "install", "gh"], capture_output=True, text=True)
            return r.returncode == 0, "brew install gh"
        return False, "Install Homebrew first or download from https://cli.github.com"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            subprocess.run(["sudo", "apt-get", "update", "-y"], capture_output=True)
            r = subprocess.run(["sudo", "apt-get", "install", "-y", "gh"], capture_output=True, text=True)
            return r.returncode == 0, "apt-get install gh"
        if shutil.which("dnf"):
            r = subprocess.run(["sudo", "dnf", "install", "-y", "gh"], capture_output=True, text=True)
            return r.returncode == 0, "dnf install gh"
        return False, "Install manually from https://cli.github.com"
    return False, f"Unsupported platform: {sysname}"
