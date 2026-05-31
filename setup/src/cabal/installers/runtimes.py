# -*- coding: utf-8 -*-
"""Language runtimes — Node/npm/pnpm/bun, Python, .NET SDK."""

from __future__ import annotations

import platform
import shutil
import subprocess

from cabal.installers._common import _run_install, _WINGET_FLAGS


def node_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "OpenJS.NodeJS.LTS", *_WINGET_FLAGS])
        if shutil.which("scoop"):
            return _run_install(["scoop", "install", "nodejs-lts"])
        return False, "Install manually from https://nodejs.org"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "node"])
        return False, "Install Homebrew or download from https://nodejs.org"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            subprocess.run(["sudo", "apt-get", "update", "-y"])
            return _run_install(["sudo", "apt-get", "install", "-y", "nodejs", "npm"])
        if shutil.which("dnf"):
            return _run_install(["sudo", "dnf", "install", "-y", "nodejs", "npm"])
        if shutil.which("pacman"):
            return _run_install(["sudo", "pacman", "-S", "--noconfirm", "nodejs", "npm"])
        return False, "Install manually from https://nodejs.org"
    return False, f"Unsupported platform: {sysname}"


def npm_install() -> tuple[bool, str]:
    # npm ships with Node.js — installing Node installs npm.
    return node_install()


def pnpm_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "pnpm.pnpm", *_WINGET_FLAGS])
        if shutil.which("npm"):
            return _run_install(["npm", "install", "-g", "pnpm"])
        return False, "Install Node/npm first, or see https://pnpm.io/installation"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "pnpm"])
        if shutil.which("npm"):
            return _run_install(["npm", "install", "-g", "pnpm"])
        return False, "Install Homebrew or see https://pnpm.io/installation"
    if sysname == "Linux":
        if shutil.which("npm"):
            return _run_install(["npm", "install", "-g", "pnpm"])
        return False, "See https://pnpm.io/installation"
    return False, f"Unsupported platform: {sysname}"


def bun_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Oven-sh.Bun", *_WINGET_FLAGS])
        if shutil.which("npm"):
            return _run_install(["npm", "install", "-g", "bun"])
        return False, "Install manually from https://bun.sh"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "oven-sh/bun/bun"])
        return False, "Install Homebrew or see https://bun.sh"
    if sysname == "Linux":
        if shutil.which("npm"):
            return _run_install(["npm", "install", "-g", "bun"])
        return False, "See https://bun.sh"
    return False, f"Unsupported platform: {sysname}"


def python_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Python.Python.3.13", *_WINGET_FLAGS])
        if shutil.which("scoop"):
            return _run_install(["scoop", "install", "python"])
        return False, "Install manually from https://www.python.org/downloads/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "python@3.13"])
        return False, "Install Homebrew or download from https://www.python.org/downloads/"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            subprocess.run(["sudo", "apt-get", "update", "-y"])
            return _run_install(["sudo", "apt-get", "install", "-y", "python3", "python3-pip", "python3-venv"])
        if shutil.which("dnf"):
            return _run_install(["sudo", "dnf", "install", "-y", "python3", "python3-pip"])
        if shutil.which("pacman"):
            return _run_install(["sudo", "pacman", "-S", "--noconfirm", "python", "python-pip"])
        return False, "Install via your distro's package manager"
    return False, f"Unsupported platform: {sysname}"


def dotnet_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Microsoft.DotNet.SDK.9", *_WINGET_FLAGS])
        return False, "Install manually from https://dotnet.microsoft.com/download"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "dotnet-sdk"])
        return False, "Install Homebrew or download from https://dotnet.microsoft.com/download"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            return _run_install(["sudo", "apt-get", "install", "-y", "dotnet-sdk-9.0"])
        if shutil.which("dnf"):
            return _run_install(["sudo", "dnf", "install", "-y", "dotnet-sdk-9.0"])
        if shutil.which("pacman"):
            return _run_install(["sudo", "pacman", "-S", "--noconfirm", "dotnet-sdk"])
        return False, "See https://learn.microsoft.com/dotnet/core/install/linux for distro-specific steps"
    return False, f"Unsupported platform: {sysname}"
