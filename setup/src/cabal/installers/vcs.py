# -*- coding: utf-8 -*-
"""Version control — Git installer."""

from __future__ import annotations

import platform
import shutil

from cabal.installers._common import _run_install, _WINGET_FLAGS


def git_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Git.Git", *_WINGET_FLAGS])
        if shutil.which("scoop"):
            return _run_install(["scoop", "install", "git"])
        return False, "Install manually from https://git-scm.com"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "git"])
        return False, "Run `xcode-select --install` or install from https://git-scm.com"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            return _run_install(["sudo", "apt-get", "install", "-y", "git"])
        if shutil.which("dnf"):
            return _run_install(["sudo", "dnf", "install", "-y", "git"])
        if shutil.which("pacman"):
            return _run_install(["sudo", "pacman", "-S", "--noconfirm", "git"])
        return False, "Install via your distro's package manager"
    return False, f"Unsupported platform: {sysname}"
