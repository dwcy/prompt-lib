# -*- coding: utf-8 -*-
"""Headroom CLI — installed via `uv tool install`, auto-provisioning the Windows Rust/MSVC build toolchain."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from cabal.installers._common import _WINGET_FLAGS
from cabal.installers.uv import uv_install

HEADROOM_SPEC = "headroom-ai[mcp]"
HEADROOM_UPGRADE_PKG = "headroom-ai"

_RUSTUP_ID = "Rustlang.Rustup"
_BUILD_TOOLS_ID = "Microsoft.VisualStudio.2022.BuildTools"
_VCTOOLS_COMPONENT = "Microsoft.VisualStudio.Component.VC.Tools.x86.x64"
_BUILD_TOOLS_OVERRIDE = (
    "--add Microsoft.VisualStudio.Workload.VCTools "
    "--includeRecommended --quiet --wait --norestart"
)
_TOOLCHAIN_TIMEOUT = 1800
_BUILD_TIMEOUT = 1800

_CARGO_BIN = Path.home() / ".cargo" / "bin"
_VSWHERE = (
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    / "Microsoft Visual Studio"
    / "Installer"
    / "vswhere.exe"
)


def headroom_status() -> str:
    if not shutil.which("headroom"):
        return "not installed"
    r = subprocess.run(["headroom", "--version"], capture_output=True, text=True)
    v = (
        (r.stdout or r.stderr or "").strip().splitlines()[0]
        if r.returncode == 0
        else ""
    )
    return f"installed {v}" if v else "installed"


def headroom_install() -> tuple[bool, str]:
    """Install or upgrade `headroom` via `uv tool install`.

    Auto-installs `uv` if missing. On Windows (no PyPI wheel) the sdist compiles
    a Rust native extension, so the Rust toolchain + MSVC C++ build tools are
    auto-provisioned via winget before the build runs.
    """
    ok, msg = _ensure_uv()
    if not ok:
        return False, msg

    if shutil.which("headroom"):
        r = subprocess.run(
            ["uv", "tool", "upgrade", HEADROOM_UPGRADE_PKG],
            capture_output=True,
            text=True,
        )
        out = (r.stdout or r.stderr or "").strip()
        return (
            r.returncode == 0,
            f"uv tool upgrade {HEADROOM_UPGRADE_PKG} — {out or 'ok'}",
        )

    if platform.system() == "Windows":
        return _install_windows()
    return _install_with_uv(env=None)


def _ensure_uv() -> tuple[bool, str]:
    """Ensure `uv` is available, auto-installing it if missing."""
    if shutil.which("uv"):
        return True, "uv present"
    ok, msg = uv_install()
    if not ok:
        return False, f"uv missing — could not auto-install ({msg})"
    if not shutil.which("uv"):
        return (
            False,
            "uv installed but not on PATH yet — open a new terminal and re-run",
        )
    return True, "uv installed"


def _install_with_uv(env: dict[str, str] | None) -> tuple[bool, str]:
    """Run `uv tool install headroom-ai[mcp]` with an optional augmented environment."""
    try:
        r = subprocess.run(
            ["uv", "tool", "install", HEADROOM_SPEC],
            capture_output=True,
            text=True,
            env=env,
            timeout=_BUILD_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"uv tool install {HEADROOM_SPEC} — failed: {e}"
    out = (r.stdout or r.stderr or "").strip()
    return r.returncode == 0, out or f"uv tool install {HEADROOM_SPEC}"


def _install_windows() -> tuple[bool, str]:
    """Provision the Rust + MSVC build toolchain, then build/install headroom from source."""
    if not shutil.which("winget"):
        return False, (
            "winget not found — install Rust (rustup) + VS Build Tools "
            "'Desktop development with C++' manually, then retry"
        )

    notes: list[str] = []
    ok, note = _ensure_rust()
    notes.append(note)
    if not ok:
        return False, " | ".join(notes)

    ok, note = _ensure_msvc_build_tools()
    notes.append(note)
    if not ok:
        return False, " | ".join(notes)

    env = dict(os.environ)
    env["PATH"] = str(_CARGO_BIN) + os.pathsep + env.get("PATH", "")
    ok, note = _install_with_uv(env=env)
    notes.append(note)
    return ok, " | ".join(notes)


def _ensure_rust() -> tuple[bool, str]:
    """Ensure a Rust toolchain (cargo) is present, installing rustup via winget if missing."""
    if shutil.which("cargo") or (_CARGO_BIN / "cargo.exe").exists():
        return True, "rust present"
    try:
        r = subprocess.run(
            ["winget", "install", "--id", _RUSTUP_ID, *_WINGET_FLAGS, "--silent"],
            capture_output=True,
            text=True,
            timeout=_TOOLCHAIN_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"rustup install failed: {e}"
    if r.returncode != 0 and not (_CARGO_BIN / "cargo.exe").exists():
        out = (r.stdout or r.stderr or "").strip()
        return False, f"rustup install failed — {out or 'winget error'}"
    return True, "rustup OK"


def _ensure_msvc_build_tools() -> tuple[bool, str]:
    """Ensure the MSVC C++ build tools are present, installing VS Build Tools via winget if missing."""
    if _has_vctools():
        return True, "VS Build Tools present"
    try:
        r = subprocess.run(
            [
                "winget",
                "install",
                "--id",
                _BUILD_TOOLS_ID,
                *_WINGET_FLAGS,
                "--override",
                _BUILD_TOOLS_OVERRIDE,
            ],
            capture_output=True,
            text=True,
            timeout=_TOOLCHAIN_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"VS Build Tools install failed: {e}"
    if r.returncode != 0 and not _has_vctools():
        out = (r.stdout or r.stderr or "").strip()
        return False, f"VS Build Tools install failed — {out or 'winget error'}"
    return True, "VS Build Tools OK"


def _has_vctools() -> bool:
    """Return True if vswhere reports the VC.Tools.x86.x64 component is installed."""
    if not _VSWHERE.exists():
        return False
    try:
        r = subprocess.run(
            [
                str(_VSWHERE),
                "-products",
                "*",
                "-latest",
                "-requires",
                _VCTOOLS_COMPONENT,
                "-property",
                "installationPath",
            ],
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and bool((r.stdout or "").strip())
