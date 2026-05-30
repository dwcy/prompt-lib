# -*- coding: utf-8 -*-
"""Apply `core.autocrlf` line-ending policy via `git config --global`."""

from __future__ import annotations

import platform
import shutil
import subprocess


def recommended_autocrlf() -> str:
    return "true" if platform.system() == "Windows" else "input"


def apply_git_line_endings(mode: str) -> tuple[bool, str]:
    if mode == "auto":
        resolved = recommended_autocrlf()
    elif mode in ("true", "input", "false"):
        resolved = mode
    else:
        return False, f"Unrecognized GIT_LINE_ENDINGS={mode!r}"
    if not shutil.which("git"):
        return False, "git not on PATH"
    result = subprocess.run(
        ["git", "config", "--global", "core.autocrlf", resolved],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True, f"git config --global core.autocrlf {resolved}"
    return False, f"git config failed: {result.stderr.strip()}"
