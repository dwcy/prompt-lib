# -*- coding: utf-8 -*-
"""AI-augmented editor installers — Cursor, Windsurf, VS Code."""

from __future__ import annotations

import platform
import shutil

from cabal.installers._common import _run_install, _WINGET_FLAGS


def cursor_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Anysphere.Cursor", *_WINGET_FLAGS])
        return False, "Install manually from https://cursor.com"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "cursor"])
        return False, "Install manually from https://cursor.com"
    return False, "Install manually from https://cursor.com"


def windsurf_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Codeium.Windsurf", *_WINGET_FLAGS])
        return False, "Install manually from https://windsurf.com"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "windsurf"])
        return False, "Install manually from https://windsurf.com"
    return False, "Install manually from https://windsurf.com"


def vscode_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Microsoft.VisualStudioCode", *_WINGET_FLAGS])
        return False, "Install manually from https://code.visualstudio.com"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "visual-studio-code"])
        return False, "Install manually from https://code.visualstudio.com"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            return _run_install(["sudo", "apt-get", "install", "-y", "code"])
        if shutil.which("dnf"):
            return _run_install(["sudo", "dnf", "install", "-y", "code"])
        return False, "Install manually from https://code.visualstudio.com"
    return False, f"Unsupported platform: {sysname}"


def zed_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Zed.Zed", *_WINGET_FLAGS])
        return False, "Install manually from https://zed.dev/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "zed"])
        return False, "Install manually from https://zed.dev/"
    if sysname == "Linux":
        return False, "Install manually from https://zed.dev/linux"
    return False, f"Unsupported platform: {sysname}"


def rider_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "JetBrains.Rider", *_WINGET_FLAGS])
        return False, "Install manually from https://www.jetbrains.com/rider/download/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "rider"])
        return False, "Install manually from https://www.jetbrains.com/rider/download/"
    if sysname == "Linux":
        if shutil.which("snap"):
            return _run_install(["snap", "install", "rider", "--classic"])
        return False, "Install manually from https://www.jetbrains.com/rider/download/"
    return False, f"Unsupported platform: {sysname}"


def visualstudio_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname != "Windows":
        return False, "Visual Studio is Windows-only. Use Rider or VS Code on this platform."
    if shutil.which("winget"):
        return _run_install(
            [
                "winget",
                "install",
                "--id",
                "Microsoft.VisualStudio.2022.Community",
                *_WINGET_FLAGS,
            ]
        )
    return False, "Install manually from https://visualstudio.microsoft.com/"
