"""Build the Cabal desktop backend sidecar with PyInstaller.

Outputs:
    setup/build/dist/cabal-backend-<target-triple>[.exe]
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import platform
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
REPO_ROOT = BUILD_DIR.parent.parent
SPEC = BUILD_DIR / "cabal-backend.spec"


def _target_triple() -> str:
    machine = platform.machine().lower()
    arch = "aarch64" if machine in {"arm64", "aarch64"} else "x86_64"
    if sys.platform == "win32":
        return f"{arch}-pc-windows-msvc"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    return f"{arch}-unknown-linux-gnu"


def main() -> int:
    work = BUILD_DIR / "build-backend"
    dist = BUILD_DIR / "dist"
    command = [
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
    print("Running:", " ".join(command))
    rc = subprocess.call(command, cwd=str(REPO_ROOT))
    if rc != 0:
        return rc

    exe = dist / f"cabal-backend-{_target_triple()}{'.exe' if sys.platform == 'win32' else ''}"
    if not exe.exists():
        print(f"Build finished but expected output was not found at {exe}", file=sys.stderr)
        return 1

    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f"Built: {exe} ({size_mb:.1f} MiB)")
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
