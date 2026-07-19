# -*- coding: utf-8 -*-
"""Local agent service action descriptors."""

from __future__ import annotations

import platform
import subprocess

from cabal import service_supervisor
from cabal.installers.a2a_bridge import a2a_bridge_install
from cabal.installers.orchestrator import orchestrator_install
from cabal.service_catalog import get_service
from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.envelope import ApiError
from cabal.webapi.services_service import service_payload, services_digest

_SERVICE_SCHEMA = {
    "type": "object",
    "properties": {"key": {"type": "string"}},
    "required": ["key"],
    "additionalProperties": False,
}

_INSTALLERS = {
    "a2a-bridge": a2a_bridge_install,
    "orchestrator": orchestrator_install,
}


def _require_key(params: dict) -> str:
    key = params["key"]
    try:
        get_service(key)
    except KeyError as exc:
        raise ApiError(422, "params_invalid", f"Unknown service {key!r}") from exc
    return key


def _setup_prepare(params: dict, _state) -> dict:
    key = _require_key(params)
    definition = get_service(key)
    return {
        "summary": f"Set up {definition.label}",
        "commands": ["uv tool install --force"],
        "files_changed": [definition.install_path],
        "scopes": ["services", key],
        "backup": None,
        "removals": [],
    }


def _setup_execute(params: dict, state) -> ActionOutcome:
    key = _require_key(params)
    installer = _INSTALLERS.get(key)
    if installer is None:
        raise ApiError(422, "params_invalid", f"{key!r} has no setup action")

    def runner(handle) -> None:
        handle.emit_line(f"Setting up {key}...")
        try:
            ok, message = installer()
        except Exception as exc:
            handle.finish("failed", exit_detail=str(exc))
            return
        for line in (message or "").splitlines():
            handle.emit_line(line)
        handle.finish("succeeded" if ok else "failed", exit_detail=None if ok else message)

    job = state.jobs.create(f"services.setup:{key}", runner=runner, exclusive_resource=f"service:{key}:setup")
    return ActionOutcome(job_id=job.job_id)


def _start_prepare(params: dict, _state) -> dict:
    key = _require_key(params)
    definition = get_service(key)
    return {
        "summary": f"Start {definition.label}",
        "commands": [definition.run_command],
        "files_changed": [str(service_supervisor.log_path(key))],
        "scopes": ["services", key],
        "backup": None,
        "removals": [],
    }


def _start_execute(params: dict, _state) -> ActionOutcome:
    key = _require_key(params)
    state = service_supervisor.start(key)
    return ActionOutcome(data=service_payload(key) | {"message": state.detail})


def _stop_prepare(params: dict, _state) -> dict:
    key = _require_key(params)
    definition = get_service(key)
    current = service_payload(key)["service"]
    process = f"{definition.label} process"
    if current.get("pid") is not None:
        process += f" (pid {current['pid']})"
    return {
        "summary": f"Stop {definition.label}",
        "commands": ["terminate service process"],
        "files_changed": [],
        "scopes": ["services", key],
        "backup": "No backup; start the service again to recover",
        "removals": [process],
    }


def _stop_execute(params: dict, _state) -> ActionOutcome:
    key = _require_key(params)
    state = service_supervisor.stop(key)
    return ActionOutcome(data=service_payload(key) | {"message": state.detail})


def _dashboard_prepare(params: dict, _state) -> dict:
    key = _require_key(params)
    definition = get_service(key)
    return {
        "summary": f"Open {definition.label} dashboard",
        "commands": [definition.dashboard_command or "dashboard unavailable"],
        "files_changed": [],
        "scopes": ["services", key, "dashboard"],
        "backup": None,
        "removals": [],
    }


def _dashboard_execute(params: dict, _state) -> ActionOutcome:
    key = _require_key(params)
    argv, message = service_supervisor.open_dashboard(key)
    if argv is None:
        raise ApiError(422, "params_invalid", message)
    if platform.system() == "Windows":
        subprocess.Popen(["cmd", "/c", "start", "Cabal Service Dashboard", *argv])
    else:
        subprocess.Popen(argv, start_new_session=True)
    return ActionOutcome(data={"key": key, "message": message, "argv": argv})


SERVICES_SETUP_DESCRIPTOR = ActionDescriptor(
    action_id="services.setup",
    module="services",
    destructive=False,
    backup_policy=None,
    params_schema=_SERVICE_SCHEMA,
    prepare=_setup_prepare,
    execute=_setup_execute,
    compute_digest=lambda params, _state: services_digest(params["key"]),
)

SERVICES_START_DESCRIPTOR = ActionDescriptor(
    action_id="services.start",
    module="services",
    destructive=False,
    backup_policy=None,
    params_schema=_SERVICE_SCHEMA,
    prepare=_start_prepare,
    execute=_start_execute,
    compute_digest=lambda params, _state: services_digest(params["key"]),
)

SERVICES_STOP_DESCRIPTOR = ActionDescriptor(
    action_id="services.stop",
    module="services",
    destructive=True,
    backup_policy=None,
    params_schema=_SERVICE_SCHEMA,
    prepare=_stop_prepare,
    execute=_stop_execute,
    compute_digest=lambda params, _state: services_digest(params["key"]),
)

SERVICES_DASHBOARD_DESCRIPTOR = ActionDescriptor(
    action_id="services.dashboard",
    module="services",
    destructive=False,
    backup_policy=None,
    params_schema=_SERVICE_SCHEMA,
    prepare=_dashboard_prepare,
    execute=_dashboard_execute,
    compute_digest=lambda params, _state: services_digest(params["key"]),
)

SERVICES_DESCRIPTORS = (
    SERVICES_SETUP_DESCRIPTOR,
    SERVICES_START_DESCRIPTOR,
    SERVICES_STOP_DESCRIPTOR,
    SERVICES_DASHBOARD_DESCRIPTOR,
)
