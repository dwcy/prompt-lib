# -*- coding: utf-8 -*-
"""uv — Astral's Python tool/version manager."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from cabal.installers._common import _WINGET_FLAGS, _run_install


def uv_tool_bin_dir() -> Path:
    """Directory uv installs tool executables into.

    Prefers `uv tool dir --bin`; falls back to uv's default user bin
    (`$XDG_BIN_HOME` or `~/.local/bin`).
    """
    if shutil.which("uv"):
        try:
            r = subprocess.run(
                ["uv", "tool", "dir", "--bin"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode == 0 and r.stdout.strip():
                return Path(r.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
    xdg = os.environ.get("XDG_BIN_HOME")
    return Path(xdg) if xdg else Path.home() / ".local" / "bin"


def ensure_uv_tool_bin_on_path() -> None:
    """Add uv's tool-bin dir to this process's PATH.

    `uv tool install` drops executables into that dir, which may not be on the
    running process's PATH; without this, `shutil.which()` cannot see a
    just-installed tool until the app restarts.
    """
    bin_str = str(uv_tool_bin_dir())
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    if bin_str not in parts:
        os.environ["PATH"] = os.pathsep.join([bin_str, *parts])


def uv_install() -> tuple[bool, str]:
    """Install `uv` using the OS-native installer. Returns (ok, message)."""
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id=astral-sh.uv", *_WINGET_FLAGS])
        return False, "Install uv manually from https://docs.astral.sh/uv/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            r = subprocess.run(["brew", "install", "uv"], capture_output=True, text=True)
            return r.returncode == 0, "brew install uv"
        return False, "Install Homebrew first or see https://docs.astral.sh/uv/"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            subprocess.run(["sudo", "apt-get", "update", "-y"], capture_output=True)
            ok, msg = _run_install(["sudo", "apt-get", "install", "-y", "uv"])
            if ok:
                return ok, msg
        if shutil.which("dnf"):
            ok, msg = _run_install(["sudo", "dnf", "install", "-y", "uv"])
            if ok:
                return ok, msg
        if shutil.which("pacman"):
            ok, msg = _run_install(["sudo", "pacman", "-S", "--noconfirm", "uv"])
            if ok:
                return ok, msg
        return (
            False,
            "Automatic Linux uv install uses only OS packages. Install uv manually from "
            "https://docs.astral.sh/uv/ if your distro does not package it.",
        )
    return False, f"Unsupported platform: {sysname}"
