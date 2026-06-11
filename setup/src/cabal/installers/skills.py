# -*- coding: utf-8 -*-
"""Skills CLI (vercel-labs/skills) — the open agent skills tool, shipped via npm."""

from __future__ import annotations

import shutil
import subprocess

from cabal.installers._common import _npm_global_install


def skills_status() -> str:
    if not shutil.which("skills"):
        return "not installed"
    r = subprocess.run(["skills", "--version"], capture_output=True, text=True)
    v = (
        (r.stdout or r.stderr or "").strip().splitlines()[0]
        if r.returncode == 0
        else ""
    )
    return f"installed {v}" if v else "installed"


def skills_install() -> tuple[bool, str]:
    # Always pull the latest published build from npm.
    return _npm_global_install("skills@latest")
