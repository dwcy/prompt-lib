# -*- coding: utf-8 -*-
"""uv — Astral's Python tool/version manager."""

from __future__ import annotations

import platform
import shutil
import subprocess

from cabal.installers._common import _WINGET_FLAGS, _run_install


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
