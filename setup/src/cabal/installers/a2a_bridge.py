# -*- coding: utf-8 -*-
"""a2a-bridge CLI — repo-local agent service installed via `uv tool install` (local checkout or git subdirectory)."""

from __future__ import annotations

import shutil
import subprocess

from cabal._paths import REPO_DIR
from cabal.installers.uv import uv_install

REPO_URL = "https://github.com/dwcy/prompt-lib"
A2A_BRIDGE_PKG = "a2a-bridge"
_SERVICE_SUBDIR = ("services", "a2a-bridge")
_GIT_SOURCE = f"git+{REPO_URL}#subdirectory=services/a2a-bridge"


def a2a_bridge_status() -> tuple[bool, str]:
    """Return (set_up, detail) via PATH presence of the console command."""
    if shutil.which(A2A_BRIDGE_PKG):
        return True, "installed"
    return False, "not installed"


def a2a_bridge_install() -> tuple[bool, str]:
    """Install or upgrade `a2a-bridge` via `uv tool install`.

    Prefers the local checkout under `REPO_DIR/services/a2a-bridge`; falls back
    to the git subdirectory when cabal runs as an installed exe/PyPI tool with
    no checkout. Returns (False, actionable message) when `uv` is missing.
    """
    if not shutil.which("uv"):
        ok, msg = uv_install()
        if not ok or not shutil.which("uv"):
            return False, (
                "uv is required to install a2a-bridge. Install uv first "
                f"(see the Tools view). ({msg})"
            )

    if shutil.which(A2A_BRIDGE_PKG):
        r = subprocess.run(
            ["uv", "tool", "upgrade", A2A_BRIDGE_PKG],
            capture_output=True,
            text=True,
        )
        out = (r.stdout or r.stderr or "").strip()
        return r.returncode == 0, f"uv tool upgrade {A2A_BRIDGE_PKG} — {out or 'ok'}"

    source = _resolve_source()
    r = subprocess.run(
        ["uv", "tool", "install", "--from", source, A2A_BRIDGE_PKG],
        capture_output=True,
        text=True,
    )
    out = (r.stdout or r.stderr or "").strip()
    return r.returncode == 0, out or f"uv tool install --from {source} {A2A_BRIDGE_PKG}"


def _resolve_source() -> str:
    """Local checkout path if present, else the git subdirectory spec."""
    if REPO_DIR is not None:
        local = REPO_DIR.joinpath(*_SERVICE_SUBDIR)
        if local.is_dir():
            return str(local)
    return _GIT_SOURCE
