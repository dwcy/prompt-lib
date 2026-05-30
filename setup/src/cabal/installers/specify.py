# -*- coding: utf-8 -*-
"""Specify CLI (GitHub Spec Kit) — installed via `uv tool install`."""

from __future__ import annotations

import shutil
import subprocess

from cabal.installers.uv import uv_install

SPECIFY_SOURCE = "git+https://github.com/github/spec-kit.git"


def specify_status() -> str:
    if not shutil.which("specify"):
        return "not installed"
    r = subprocess.run(["specify", "--version"], capture_output=True, text=True)
    v = (r.stdout or r.stderr or "").strip().splitlines()[0] if r.returncode == 0 else ""
    return f"installed {v}" if v else "installed"


def specify_install() -> tuple[bool, str]:
    """Install or upgrade `specify` via `uv tool install`. Auto-installs uv if missing."""
    if not shutil.which("uv"):
        ok, msg = uv_install()
        if not ok:
            return False, f"uv missing — could not auto-install ({msg})"
        if not shutil.which("uv"):
            return False, "uv installed but not on PATH yet — open a new terminal and re-run"

    if shutil.which("specify"):
        r = subprocess.run(
            ["uv", "tool", "upgrade", "specify-cli"],
            capture_output=True, text=True,
        )
        out = (r.stdout or r.stderr or "").strip()
        return r.returncode == 0, f"uv tool upgrade specify-cli — {out or 'ok'}"

    r = subprocess.run(
        ["uv", "tool", "install", "specify-cli", "--from", SPECIFY_SOURCE],
        capture_output=True, text=True,
    )
    out = (r.stdout or r.stderr or "").strip()
    return r.returncode == 0, out or "uv tool install specify-cli"
