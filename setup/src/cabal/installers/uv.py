# -*- coding: utf-8 -*-
"""uv — Astral's Python tool/version manager."""

from __future__ import annotations

import platform
import shutil
import subprocess


def uv_install() -> tuple[bool, str]:
    """Install `uv` using the OS-native installer. Returns (ok, message)."""
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            r = subprocess.run(
                ["winget", "install", "--id", "astral-sh.uv", "-e", "--silent",
                 "--accept-source-agreements", "--accept-package-agreements"],
                capture_output=True, text=True,
            )
            return r.returncode == 0, "winget install astral-sh.uv"
        return False, "Install uv manually from https://docs.astral.sh/uv/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            r = subprocess.run(["brew", "install", "uv"], capture_output=True, text=True)
            return r.returncode == 0, "brew install uv"
        return False, "Install Homebrew first or see https://docs.astral.sh/uv/"
    if sysname == "Linux":
        r = subprocess.run(
            ["bash", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
            capture_output=True, text=True,
        )
        return r.returncode == 0, "astral uv installer (curl)"
    return False, f"Unsupported platform: {sysname}"
