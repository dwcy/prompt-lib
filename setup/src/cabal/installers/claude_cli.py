# -*- coding: utf-8 -*-
"""Claude CLI (claude-code) — Anthropic's terminal interface."""

from __future__ import annotations

import shutil
import subprocess

from cabal.installers._common import _npm_global_install, _run_install


def claude_cli_status() -> str:
    exe = shutil.which("claude")
    if not exe:
        return "not installed"
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError):
        return "installed"
    v = (
        (r.stdout or r.stderr or "").strip().splitlines()[0]
        if r.returncode == 0
        else ""
    )
    return f"installed {v}" if v else "installed"


def claude_cli_install() -> tuple[bool, str]:
    # Use `claude update` when installed so we update the PATH-active variant
    # (native installer vs npm shim); fall back to npm for first install.
    if shutil.which("claude"):
        return _run_install(["claude", "update"])
    return _npm_global_install("@anthropic-ai/claude-code")
