# -*- coding: utf-8 -*-
"""Developer utility installers: Postman, Hugo, Uvicorn."""

from __future__ import annotations

import platform
import shutil

from cabal.installers._common import _run_install, _WINGET_FLAGS


def postman_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Postman.Postman", *_WINGET_FLAGS])
        return False, "Install manually from https://www.postman.com/downloads/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "postman"])
        return False, "Install manually from https://www.postman.com/downloads/"
    if sysname == "Linux":
        if shutil.which("snap"):
            return _run_install(["snap", "install", "postman"])
        return False, "Install manually from https://www.postman.com/downloads/"
    return False, f"Unsupported platform: {sysname}"


def hugo_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Hugo.Hugo.Extended", *_WINGET_FLAGS])
        if shutil.which("choco"):
            return _run_install(["choco", "install", "hugo-extended", "-y"])
        return False, "Install manually from https://gohugo.io/installation/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "hugo"])
        return False, "Install manually from https://gohugo.io/installation/"
    if sysname == "Linux":
        if shutil.which("snap"):
            return _run_install(["snap", "install", "hugo"])
        if shutil.which("apt-get"):
            return _run_install(["sudo", "apt-get", "install", "-y", "hugo"])
        return False, "Install manually from https://gohugo.io/installation/"
    return False, f"Unsupported platform: {sysname}"


def uvicorn_install() -> tuple[bool, str]:
    if shutil.which("uv"):
        return _run_install(["uv", "tool", "install", "uvicorn"])
    if shutil.which("pipx"):
        return _run_install(["pipx", "install", "uvicorn"])
    if shutil.which("python"):
        return _run_install(["python", "-m", "pip", "install", "--user", "uvicorn"])
    return False, "Python not found - install Python first, then install Uvicorn."
