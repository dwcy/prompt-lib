"""Discover and stop local processes that expose TCP listening ports."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psutil

from cabal.webapi.envelope import ApiError, compute_precondition_digest

_GENERIC_PROCESS_NAMES = {
    "bun",
    "bun.exe",
    "deno",
    "deno.exe",
    "dotnet",
    "dotnet.exe",
    "node",
    "node.exe",
    "php",
    "php.exe",
    "python",
    "python.exe",
    "python3",
    "python3.exe",
    "ruby",
    "ruby.exe",
}


def running_apps_payload() -> dict[str, Any]:
    """Return one row per TCP listening port, grouped by owning process."""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for connection in _tcp_connections():
        pid = getattr(connection, "pid", None)
        if pid is None or pid == os.getpid() or connection.status != psutil.CONN_LISTEN:
            continue
        address, port = _local_address(connection)
        if port is None or (pid, port) in seen:
            continue
        seen.add((pid, port))
        row = _process_row(pid, port, address)
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda row: (row["port"], row["pid"]))
    return {"apps": rows, "count": len(rows)}


def find_running_app(pid: int, port: int, started_at: float) -> dict[str, Any]:
    """Resolve a stable listener identity and reject stale/reused PIDs."""
    for row in running_apps_payload()["apps"]:
        if (
            row["pid"] == pid
            and row["port"] == port
            and abs(row["started_at"] - started_at) < 0.001
        ):
            return row
    raise ApiError(
        404,
        "running_app_not_found",
        f"No running app is listening on port {port} with PID {pid}",
    )


def running_app_digest(pid: int, port: int, started_at: float) -> str:
    return compute_precondition_digest(find_running_app(pid, port, started_at))


def stop_running_app(pid: int, port: int, started_at: float) -> dict[str, Any]:
    """Terminate the verified listener, escalating to kill after a short grace period."""
    app = find_running_app(pid, port, started_at)
    if pid == os.getpid():
        raise ApiError(422, "params_invalid", "Cabal cannot shut down its own backend")

    try:
        process = psutil.Process(pid)
        if abs(process.create_time() - started_at) >= 0.001:
            raise ApiError(409, "state_changed", "The process identity changed; refresh and retry")
        process.terminate()
        try:
            process.wait(timeout=3)
        except psutil.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied as exc:
        raise ApiError(
            403,
            "process_access_denied",
            f"Permission denied while shutting down PID {pid}",
        ) from exc
    return {"stopped": True, "app": app}


def _tcp_connections() -> list[Any]:
    try:
        return list(psutil.net_connections(kind="tcp"))
    except (psutil.AccessDenied, OSError):
        connections: list[Any] = []
        for process in psutil.process_iter():
            try:
                for connection in process.net_connections(kind="tcp"):
                    connections.append(
                        SimpleNamespace(
                            pid=process.pid,
                            status=connection.status,
                            laddr=connection.laddr,
                        )
                    )
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                continue
        return connections


def _local_address(connection: Any) -> tuple[str, int | None]:
    local = getattr(connection, "laddr", None)
    if not local:
        return "", None
    address = getattr(local, "ip", None)
    port = getattr(local, "port", None)
    if address is None and isinstance(local, tuple) and len(local) >= 2:
        address, port = local[0], local[1]
    return str(address or ""), int(port) if port is not None else None


def _process_row(pid: int, port: int, address: str) -> dict[str, Any] | None:
    try:
        process = psutil.Process(pid)
        with process.oneshot():
            process_name = process.name() or f"PID {pid}"
            started_at = process.create_time()
            location = _process_location(process)
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return None
    app_name = _manifest_name(location) or _fallback_app_name(process_name, location)
    return {
        "port": port,
        "pid": pid,
        "app_name": app_name,
        "location": str(location) if location is not None else None,
        "address": address,
        "started_at": started_at,
    }


def _process_location(process: psutil.Process) -> Path | None:
    try:
        cwd = process.cwd()
        if cwd:
            return Path(cwd)
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        pass
    try:
        executable = process.exe()
        if executable:
            return Path(executable).parent
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        pass
    return None


def _manifest_name(location: Path | None) -> str | None:
    if location is None:
        return None
    candidates = [location, *list(location.parents)[:3]]
    for directory in candidates:
        package_json = directory / "package.json"
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            name = data.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            pass

        pyproject = directory / "pyproject.toml"
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            name = data.get("project", {}).get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):
            pass
    return None


def _fallback_app_name(process_name: str, location: Path | None) -> str:
    if process_name.casefold() in _GENERIC_PROCESS_NAMES and location is not None:
        return location.name or process_name
    suffix = Path(process_name).suffix
    return process_name[: -len(suffix)] if suffix.casefold() == ".exe" else process_name
