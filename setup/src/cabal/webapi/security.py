"""Bearer-token auth, atomic handshake lifecycle, owner-only ACLs, and locked CORS."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from cabal.webapi.envelope import ApiError

HANDSHAKE_SCHEMA = "cabal-handshake.v1"

TAURI_ORIGINS = (
    "tauri://localhost",
    "http://tauri.localhost",
)
# Only reachable while a Vite dev server is actually running; in a packaged build
# they would hand any local process that can bind 5173 a blessed origin against a
# mutation-capable backend.
DEV_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)
DEV_MODE_ENV_VAR = "CABAL_DEV"

_STILL_ACTIVE = 259
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def write_handshake_atomic(path: Path, *, port: int, token: str, pid: int, started_at: str) -> None:
    """Write the handshake via temp-file + os.replace so no partial read is possible."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": HANDSHAKE_SCHEMA,
        "port": port,
        "token": token,
        "pid": pid,
        "started_at": started_at,
    }
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".handshake-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        # Restrict BEFORE the rename: the DACL/mode travels with the file, so the
        # handshake is never observable in an unrestricted state.
        restrict_to_owner(Path(tmp_name))
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def read_handshake(path: Path) -> dict | None:
    """Return the handshake payload, or None when the file is absent, corrupt, or stale.

    A handshake whose recorded pid is no longer alive is treated as corrupt: hard-killed
    backends cannot clean up their file, and no consumer may ever adopt a dead backend.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema") != HANDSHAKE_SCHEMA:
        return None
    port = data.get("port")
    token = data.get("token")
    started_at = data.get("started_at")
    if not isinstance(port, int) or not 0 < port <= 65535:
        return None
    if not isinstance(token, str) or not token:
        return None
    if not isinstance(started_at, str) or not started_at:
        return None
    pid = data.get("pid")
    if not isinstance(pid, int) or not is_pid_alive(pid):
        return None
    return data


def remove_handshake(
    path: Path,
    *,
    expected_token: str | None = None,
    expected_pid: int | None = None,
) -> bool:
    """Remove a handshake only when it still belongs to the expected backend."""
    path = Path(path)
    if expected_token is not None or expected_pid is not None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if expected_token is not None and data.get("token") != expected_token:
            return False
        if expected_pid is not None and data.get("pid") != expected_pid:
            return False
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return False
    return True


def restrict_to_owner(path: Path) -> None:
    """Apply the platform owner-only protection (icacls ACL on Windows, chmod 0600 on POSIX)."""
    path = Path(path)
    if sys.platform == "win32":
        account = _windows_account()
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{account}:F"],
            check=True,
            capture_output=True,
        )
    else:
        path.chmod(0o600)


def handshake_is_owner_restricted(path: Path) -> bool:
    """Truth source for the owner-only guarantee; owns the POSIX-mode-vs-Windows-ACL branching."""
    path = Path(path)
    if not path.exists():
        return False
    if sys.platform == "win32":
        result = subprocess.run(["icacls", str(path)], capture_output=True, text=True)
        if result.returncode != 0:
            return False
        aces = _parse_icacls_aces(result.stdout, path)
        username = os.environ.get("USERNAME", "").lower()
        return bool(aces) and bool(username) and all(username in ace.lower() for ace in aces)
    return (path.stat().st_mode & 0o077) == 0


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _windows_pid_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def effective_server_pid() -> int:
    """Pid to advertise in the handshake.

    On Windows, the venv/uv `python.exe` is a launcher that spawns the real
    interpreter as a child, so the pid the spawner (desktop shell, tests) holds is
    our parent's. When the parent's image is exactly our `sys.executable`, report
    the parent pid — that is the process handle the outside world can watch/kill.
    """
    pid = os.getpid()
    if sys.platform != "win32":
        return pid
    parent = os.getppid()
    if parent <= 0:
        return pid
    parent_image = _windows_process_image(parent)
    if parent_image is not None and _same_path(parent_image, sys.executable):
        return parent
    return pid


def require_bearer_token(request: Request) -> None:
    """FastAPI dependency: every /api route demands the handshake bearer token."""
    expected = getattr(request.app.state, "token", None)
    header = request.headers.get("authorization", "")
    scheme, _, credentials = header.partition(" ")
    if (
        not expected
        or scheme.lower() != "bearer"
        or not secrets.compare_digest(credentials.strip(), expected)
    ):
        raise ApiError(401, "unauthorized", "Missing or invalid bearer token")


def dev_mode_enabled() -> bool:
    return os.environ.get(DEV_MODE_ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}


def allowed_origins(*, dev: bool | None = None) -> list[str]:
    """Tauri origins always; the Vite dev origins only when dev mode is signalled."""
    allow_dev = dev_mode_enabled() if dev is None else dev
    return list(TAURI_ORIGINS) + (list(DEV_ORIGINS) if allow_dev else [])


def apply_cors(app: FastAPI, *, dev: bool | None = None) -> None:
    """CORS locked to the Tauri origins, plus the Vite dev origins in dev mode only."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(dev=dev),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
    )


def _windows_account() -> str:
    username = os.environ.get("USERNAME", "")
    domain = os.environ.get("USERDOMAIN", "")
    return f"{domain}\\{username}" if domain else username


def _parse_icacls_aces(stdout: str, path: Path) -> list[str]:
    path_text = str(path)
    aces: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("successfully processed"):
            continue
        if line.startswith(path_text):
            line = line[len(path_text) :].strip()
        if ":(" in line:
            aces.append(line)
    return aces


def _windows_pid_alive(pid: int) -> bool:
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        # Access denied means the process exists but is not ours.
        return ctypes.get_last_error() == 5 or kernel32.GetLastError() == 5
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _windows_process_image(pid: int) -> str | None:
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def _same_path(left: str, right: str) -> bool:
    try:
        return Path(left).resolve() == Path(right).resolve()
    except OSError:
        return False
