"""Build the standalone CABAL Setup Wizard executable.

Cross-platform driver around PyInstaller. On any OS:

    python setup/build/build_exe.py

Outputs:
    setup/build/dist/cabal            (Linux / macOS)
    setup/build/dist/cabal.exe        (Windows)

Run mode parity:
    - Installed:  cabal
    - Dev:        python setup/settings-configurator-ui.py
    - Frozen:     ./cabal[.exe]

All three modes resolve `global/`, `setup/env/`, and `setup/mcp-templates.json`
via the same code path in the wizard — see `_resource_root()` and
`_detect_repo_dir()` in `setup/src/cabal/wizard.py`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
REPO_ROOT = BUILD_DIR.parent.parent
SPEC = BUILD_DIR / "cabal.spec"


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
        return
    except ImportError:
        pass
    print("PyInstaller not installed — installing into the current interpreter...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def _ensure_textual() -> None:
    try:
        import textual  # noqa: F401
        return
    except ImportError:
        pass
    print("textual not installed — installing into the current interpreter...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "textual"])


def main() -> int:
    _ensure_pyinstaller()
    _ensure_textual()

    work = BUILD_DIR / "build"
    dist = BUILD_DIR / "dist"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath",
        str(work),
        "--distpath",
        str(dist),
        str(SPEC),
    ]
    print("Running:", " ".join(cmd))
    rc = subprocess.call(cmd, cwd=str(REPO_ROOT))
    if rc != 0:
        return rc

    exe = dist / ("cabal.exe" if sys.platform == "win32" else "cabal")
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"\nBuilt: {exe}  ({size_mb:.1f} MiB)")
    else:
        print(f"\nBuild finished but expected output not found at {exe}")
        return 1

    # Drop the intermediate work tree once we have the exe.
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
