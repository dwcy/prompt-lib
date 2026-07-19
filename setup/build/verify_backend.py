"""Smoke-check the packaged Cabal backend sidecar.

This is not a test suite. It verifies the T095 packaging contract:

1. start the PyInstaller-built cabal-backend binary
2. wait for the handshake file
3. call /api/health with the handshake bearer token
4. request graceful shutdown and clean up the temporary files
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BUILD_DIR = Path(__file__).resolve().parent
REPO_ROOT = BUILD_DIR.parent.parent


def _target_triple() -> str:
    machine = platform.machine().lower()
    arch = "aarch64" if machine in {"arm64", "aarch64"} else "x86_64"
    if sys.platform == "win32":
        return f"{arch}-pc-windows-msvc"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    return f"{arch}-unknown-linux-gnu"


def _default_exe() -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return BUILD_DIR / "dist" / f"cabal-backend-{_target_triple()}{suffix}"


def _request_json(url: str, token: str, *, method: str = "GET") -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_handshake(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _process_flags() -> int:
    if sys.platform == "win32":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify the packaged cabal-backend sidecar.")
    parser.add_argument("--exe", type=Path, default=_default_exe(), help="Packaged sidecar binary to run")
    parser.add_argument("--project", type=Path, default=REPO_ROOT, help="Project directory for the backend")
    parser.add_argument("--timeout", type=float, default=30.0, help="Seconds to wait for the handshake")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    exe = args.exe.resolve()
    if not exe.exists():
        print(f"missing sidecar binary: {exe}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="cabal-backend-smoke-") as tmp:
        tmp_path = Path(tmp)
        handshake = tmp_path / "handshake.json"
        storage = tmp_path / "webapi.sqlite3"
        startup_log = tmp_path / "startup.log"
        env = os.environ.copy()
        env["CABAL_BACKEND_STARTUP_LOG"] = str(startup_log)
        command = [
            str(exe),
            "--handshake-path",
            str(handshake),
            "--storage-path",
            str(storage),
            "--project",
            str(args.project.resolve()),
        ]
        process = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            creationflags=_process_flags(),
        )
        try:
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                if handshake.exists():
                    break
                if process.poll() is not None:
                    stdout, stderr = process.communicate(timeout=1)
                    print(f"sidecar exited before handshake: {process.returncode}", file=sys.stderr)
                    _print_failure_context(stdout, stderr, startup_log)
                    return 1
                time.sleep(0.1)

            if not handshake.exists():
                print("sidecar did not write handshake before timeout", file=sys.stderr)
                _stop(process)
                stdout, stderr = process.communicate(timeout=2)
                _print_failure_context(stdout, stderr, startup_log)
                return 1

            payload = _read_handshake(handshake)
            token = str(payload["token"])
            port = int(payload["port"])
            health = _request_json(f"http://127.0.0.1:{port}/api/health", token)
            shutdown = _request_json(f"http://127.0.0.1:{port}/api/system/shutdown", token, method="POST")
            process.wait(timeout=10)
            print(f"sidecar: {exe.name}")
            print(f"handshake: {payload.get('schema')} port={port}")
            print(f"health: {health.get('status')} modules={len(health.get('data', {}).get('modules', []))}")
            print(f"shutdown: stopping={shutdown.get('data', {}).get('stopping')}")
            return 0
        except (KeyError, ValueError, OSError, urllib.error.URLError, subprocess.TimeoutExpired) as exc:
            print(f"sidecar smoke failed: {exc}", file=sys.stderr)
            _stop(process)
            stdout, stderr = process.communicate(timeout=2)
            _print_failure_context(stdout, stderr, startup_log)
            return 1
        finally:
            if process.poll() is None:
                _stop(process)


def _stop(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _print_failure_context(stdout: str, stderr: str, startup_log: Path) -> None:
    if startup_log.exists():
        print("startup log:", file=sys.stderr)
        print(startup_log.read_text(encoding="utf-8").strip(), file=sys.stderr)
    if stdout.strip():
        print("stdout:", file=sys.stderr)
        print(stdout.strip(), file=sys.stderr)
    if stderr.strip():
        print("stderr:", file=sys.stderr)
        print(stderr.strip(), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
