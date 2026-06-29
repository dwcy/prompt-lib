# -*- coding: utf-8 -*-
"""mcp-bus CLI — repo-local MCP service installed via `uv tool install` (local checkout or git subdirectory)."""

from __future__ import annotations

import shutil
import subprocess

from cabal._paths import REPO_DIR
from cabal.installers.uv import uv_install

REPO_URL = "https://github.com/dwcy/prompt-lib"
MCP_BUS_PKG = "mcp-bus"
_SERVICE_SUBDIR = ("services", "mcp-bus")
_GIT_SOURCE = f"git+{REPO_URL}#subdirectory=services/mcp-bus"


def mcp_bus_status() -> str:
    if not shutil.which(MCP_BUS_PKG):
        return "not installed"
    r = subprocess.run([MCP_BUS_PKG, "--version"], capture_output=True, text=True)
    v = (
        (r.stdout or r.stderr or "").strip().splitlines()[0]
        if r.returncode == 0
        else ""
    )
    return f"installed {v}" if v else "installed"


def mcp_bus_install() -> tuple[bool, str]:
    """Install or upgrade `mcp-bus` via `uv tool install`.

    Auto-installs `uv` if missing. Prefers the local checkout under
    `REPO_DIR/services/mcp-bus`; falls back to the git subdirectory when cabal
    runs as an installed exe/PyPI tool with no checkout.
    """
    ok, msg = _ensure_uv()
    if not ok:
        return False, msg

    if shutil.which(MCP_BUS_PKG):
        r = subprocess.run(
            ["uv", "tool", "upgrade", MCP_BUS_PKG],
            capture_output=True,
            text=True,
        )
        out = (r.stdout or r.stderr or "").strip()
        return r.returncode == 0, f"uv tool upgrade {MCP_BUS_PKG} — {out or 'ok'}"

    source = _resolve_source()
    if source is None:
        return False, (
            "Could not resolve an mcp-bus source — no local checkout at "
            "REPO_DIR/services/mcp-bus and no git fallback available. Install "
            f"manually: uv tool install --from {_GIT_SOURCE} {MCP_BUS_PKG}"
        )

    r = subprocess.run(
        ["uv", "tool", "install", "--from", source, MCP_BUS_PKG],
        capture_output=True,
        text=True,
    )
    out = (r.stdout or r.stderr or "").strip()
    return r.returncode == 0, out or f"uv tool install --from {source} {MCP_BUS_PKG}"


def _resolve_source() -> str | None:
    """Local checkout path if present, else the git subdirectory spec."""
    if REPO_DIR is not None:
        local = REPO_DIR.joinpath(*_SERVICE_SUBDIR)
        if local.is_dir():
            return str(local)
    return _GIT_SOURCE


def _ensure_uv() -> tuple[bool, str]:
    """Ensure `uv` is available, auto-installing it if missing."""
    if shutil.which("uv"):
        return True, "uv present"
    ok, msg = uv_install()
    if not ok:
        return False, f"uv missing — could not auto-install ({msg})"
    if not shutil.which("uv"):
        return (
            False,
            "uv installed but not on PATH yet — open a new terminal and re-run",
        )
    return True, "uv installed"
