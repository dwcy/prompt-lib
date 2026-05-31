# -*- coding: utf-8 -*-
"""claude-devtools — desktop GUI for visualising Claude Code sessions."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from cabal.gh_release import _gh_latest_release, _gh_pick_asset, _download

CDT_REPO = "matt1398/claude-devtools"


def _cdt_windows_exe() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Programs" / "claude-devtools" / "claude-devtools.exe"


def cdt_status() -> str:
    sysname = platform.system()
    if sysname == "Windows":
        exe = _cdt_windows_exe()
        if not exe.exists():
            return "not installed"
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"(Get-Item '{exe}').VersionInfo.FileVersion"],
            capture_output=True, text=True,
        )
        v = (ps.stdout or "").strip()
        return f"installed {v}" if v else "installed"
    if sysname == "Darwin":
        if shutil.which("brew"):
            r = subprocess.run(
                ["brew", "list", "--cask", "--versions", "claude-devtools"],
                capture_output=True, text=True,
            )
            if r.returncode == 0 and r.stdout.strip():
                return f"installed ({r.stdout.strip()})"
        if Path("/Applications/claude-devtools.app").exists():
            return "installed"
        return "not installed"
    if sysname == "Linux":
        for p in ("/usr/bin/claude-devtools", "/opt/claude-devtools/claude-devtools"):
            if Path(p).exists():
                return f"installed ({p})"
        return "not installed"
    return "unsupported platform"


def cdt_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Darwin":
        if not shutil.which("brew"):
            return False, "Homebrew not found — install brew or download from claude-dev.tools"
        r = subprocess.run(["brew", "install", "--cask", "claude-devtools"])
        return r.returncode == 0, "brew install --cask claude-devtools"

    try:
        release = _gh_latest_release(CDT_REPO)
    except Exception as e:
        return False, f"GitHub API failed: {e}"
    tag = release.get("tag_name", "")

    if sysname == "Windows":
        asset = _gh_pick_asset(release, "-x64.exe")
        if not asset:
            return False, "No Windows installer in latest release"
        tmp_root = Path(os.environ.get("TEMP") or Path.home())
        tmp = tmp_root / asset["name"]
        try:
            _download(asset["browser_download_url"], tmp)
        except Exception as e:
            return False, f"Download failed: {e}"
        r = subprocess.run([str(tmp), "/S"])
        if r.returncode != 0:
            return False, f"Installer exit code {r.returncode}"
        return True, f"Installed {tag} from {asset['name']}"

    if sysname == "Linux":
        if shutil.which("dnf"):
            asset, installer = _gh_pick_asset(release, ".rpm"), ["sudo", "dnf", "install", "-y"]
        elif shutil.which("apt-get"):
            asset, installer = _gh_pick_asset(release, ".deb"), ["sudo", "apt-get", "install", "-y"]
        elif shutil.which("pacman"):
            asset, installer = _gh_pick_asset(release, ".pacman"), ["sudo", "pacman", "-U", "--noconfirm"]
        else:
            return False, "No supported package manager (need dnf, apt-get, or pacman)"
        if not asset:
            return False, "No matching Linux package in latest release"
        tmp = Path("/tmp") / asset["name"]
        try:
            _download(asset["browser_download_url"], tmp)
        except Exception as e:
            return False, f"Download failed: {e}"
        r = subprocess.run([*installer, str(tmp)])
        return r.returncode == 0, f"Installed {tag}"

    return False, f"Unsupported platform: {sysname}"
