# -*- coding: utf-8 -*-
"""orchestrator CLI — repo-local agent service installed via `uv tool install` (local checkout or git subdirectory)."""

from __future__ import annotations

import shutil
import subprocess

from cabal._paths import REPO_DIR
from cabal.installers.uv import ensure_uv_tool_bin_on_path, uv_install

REPO_URL = "https://github.com/dwcy/prompt-lib"
ORCHESTRATOR_PKG = "orchestrator"
_SERVICE_SUBDIR = ("services", "orchestrator")
_GIT_SOURCE = f"git+{REPO_URL}#subdirectory=services/orchestrator"


def orchestrator_status() -> tuple[bool, str]:
    """Return (set_up, detail) via PATH presence of the console command."""
    if shutil.which(ORCHESTRATOR_PKG):
        return True, "installed"
    return False, "not installed"


def orchestrator_install() -> tuple[bool, str]:
    """Install or upgrade `orchestrator` via `uv tool install`.

    Prefers the local checkout under `REPO_DIR/services/orchestrator`; falls
    back to the git subdirectory when cabal runs as an installed exe/PyPI tool
    with no checkout. Returns (False, actionable message) when `uv` is missing.

    orchestrator declares a path-dependency on a2a-bridge. Installing from the
    local checkout resolves that sibling path dep relative to orchestrator's
    pyproject; the git-subdirectory fallback cannot pull a sibling path dep, so
    the local checkout is preferred and the fallback message points the
    maintainer at installing a2a-bridge first.
    """
    if not shutil.which("uv"):
        ok, msg = uv_install()
        if not ok or not shutil.which("uv"):
            return False, (
                "uv is required to install orchestrator. Install uv first "
                f"(see the Tools view). ({msg})"
            )

    # Make uv's tool-bin dir visible to this process so a fresh install resolves
    # on PATH immediately (no app restart needed to see / start the service).
    ensure_uv_tool_bin_on_path()

    if shutil.which(ORCHESTRATOR_PKG):
        r = subprocess.run(
            ["uv", "tool", "upgrade", ORCHESTRATOR_PKG],
            capture_output=True,
            text=True,
        )
        out = (r.stdout or r.stderr or "").strip()
        return r.returncode == 0, f"uv tool upgrade {ORCHESTRATOR_PKG} — {out or 'ok'}"

    source, is_local = _resolve_source()
    r = subprocess.run(
        ["uv", "tool", "install", "--from", source, ORCHESTRATOR_PKG],
        capture_output=True,
        text=True,
    )
    out = (r.stdout or r.stderr or "").strip()
    if r.returncode == 0:
        return True, out or f"uv tool install --from {source} {ORCHESTRATOR_PKG}"
    if not is_local:
        out = (
            f"{out} — orchestrator depends on a2a-bridge; install a2a-bridge "
            "first or run from a local checkout so the path dependency resolves."
        ).strip()
    return False, out


def _resolve_source() -> tuple[str, bool]:
    """(source, is_local): local checkout path if present, else the git subdirectory spec."""
    if REPO_DIR is not None:
        local = REPO_DIR.joinpath(*_SERVICE_SUBDIR)
        if local.is_dir():
            return str(local), True
    return _GIT_SOURCE, False
