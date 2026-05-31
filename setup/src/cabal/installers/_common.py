# -*- coding: utf-8 -*-
"""Shared installer plumbing — capture-mode subprocess runner + npm-global helper."""

from __future__ import annotations

import shutil
import subprocess

_WINGET_FLAGS = ["-e", "--accept-source-agreements", "--accept-package-agreements"]


def _run_install(cmd: list[str]) -> tuple[bool, str]:
    """Resolve argv[0] via PATH (handles Windows .CMD shims), capture output.

    Output is captured (not streamed) so the EnvPanel install worker can
    display the result inside the TUI rather than dumping into the terminal.
    """
    head, *rest = cmd
    resolved = shutil.which(head) or head
    try:
        r = subprocess.run(
            [resolved, *rest], capture_output=True, text=True, timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"failed to launch: {e}"
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    return r.returncode == 0, out or " ".join(cmd)


def _npm_global_install(pkg: str) -> tuple[bool, str]:
    if not shutil.which("npm"):
        return False, "npm not found — install Node.js first"
    return _run_install(["npm", "install", "-g", pkg])
