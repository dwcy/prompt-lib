# -*- coding: utf-8 -*-
"""Web payloads for local agent services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cabal import service_prereqs, service_supervisor
from cabal.service_catalog import ServiceDefinition, ServiceState, ServiceStatus, all_services, get_service
from cabal.webapi.envelope import ApiError, compute_precondition_digest


def _definition(key: str) -> ServiceDefinition:
    try:
        return get_service(key)
    except KeyError as exc:
        raise ApiError(404, "service_not_found", f"Unknown service {key!r}") from exc


def _prereqs(key: str) -> list[dict[str, Any]]:
    return [
        {"key": item.name, "ok": bool(item.ok), "message": item.message}
        for item in service_prereqs.check(key)
    ]


def _state_payload(definition: ServiceDefinition, state: ServiceState) -> dict[str, Any]:
    log_path = service_supervisor.log_path(definition.key)
    return {
        "key": definition.key,
        "label": definition.label,
        "description": definition.description,
        "state": state.status.value,
        "detail": state.detail,
        "run_command": definition.run_command,
        "source_url": definition.source_url,
        "runnable": definition.runnable,
        "depends_on": list(definition.depends_on),
        "install_path": definition.install_path,
        "console_name": definition.console_name,
        "pid": state.pid,
        "started_by_app": state.started_by_cabal,
        "prereqs": _prereqs(definition.key),
        "log_stream_available": definition.runnable,
        "log_path": str(log_path),
        "log_present": log_path.exists(),
        "dashboard_handoff": bool(definition.dashboard_command),
        "dashboard_command": definition.dashboard_command,
        "default_port": definition.default_port,
    }


def services_payload() -> dict[str, Any]:
    states = service_supervisor.statuses()
    rows = [
        _state_payload(definition, states.get(definition.key) or service_supervisor.status(definition.key))
        for definition in all_services()
    ]
    counts = {
        "total": len(rows),
        "running": sum(1 for row in rows if row["state"] == ServiceStatus.RUNNING.value),
        "stopped": sum(1 for row in rows if row["state"] == ServiceStatus.STOPPED.value),
        "not_set_up": sum(1 for row in rows if row["state"] == ServiceStatus.NOT_SET_UP.value),
        "blocked": sum(1 for row in rows if row["state"] == ServiceStatus.BLOCKED.value),
    }
    return {"services": rows, "counts": counts}


def service_payload(key: str) -> dict[str, Any]:
    definition = _definition(key)
    return {"service": _state_payload(definition, service_supervisor.status(key))}


def service_log_snapshot(key: str, *, tail_lines: int = 120) -> dict[str, Any]:
    path = service_log_path(key)
    if not path.exists():
        return {"key": key, "path": str(path), "lines": []}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"key": key, "path": str(path), "lines": lines[-tail_lines:]}


def service_log_path(key: str) -> Path:
    """Resolve a catalog-owned log path; arbitrary route keys never reach the filesystem."""
    definition = _definition(key)
    return service_supervisor.log_path(definition.key)


def services_digest(key: str | None = None) -> str:
    payload = service_payload(key) if key else services_payload()
    return compute_precondition_digest(payload)
