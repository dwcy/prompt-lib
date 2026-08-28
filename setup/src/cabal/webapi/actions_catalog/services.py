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
from cabal.webapi.docker_apps_service import (
    docker_container_digest,
    find_docker_container,
    start_docker_container,
    stop_docker_container,
)
from cabal.webapi.envelope import ApiError
from cabal.webapi.running_apps_service import (
    find_running_app,
    running_app_digest,
    stop_running_app,
)
from cabal.webapi.services_service import service_payload, services_digest

_SERVICE_SCHEMA = {
    "type": "object",
    "properties": {"key": {"type": "string"}},
    "required": ["key"],
    "additionalProperties": False,
}

_RUNNING_APP_SCHEMA = {
    "type": "object",
    "properties": {
        "pid": {"type": "integer", "minimum": 1},
        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
        "started_at": {"type": "number"},
    },
    "required": ["pid", "port", "started_at"],
    "additionalProperties": False,
}

_DOCKER_CONTAINER_SCHEMA = {
    "type": "object",
    "properties": {
        "container_id": {"type": "string"},
        "expected_state": {"type": "string"},
    },
    "required": ["container_id", "expected_state"],
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


def _running_app_stop_prepare(params: dict, _state) -> dict:
    app = find_running_app(params["pid"], params["port"], params["started_at"])
    label = f"{app['app_name']} (PID {app['pid']}, port {app['port']})"
    return {
        "summary": f"Shut down {app['app_name']} on port {app['port']}",
        "commands": [f"terminate process {app['pid']}"],
        "files_changed": [],
        "scopes": ["services", "running-apps", str(app["pid"])],
        "backup": "Restart the app from its location or original command",
        "removals": [label],
    }


def _running_app_stop_execute(params: dict, _state) -> ActionOutcome:
    return ActionOutcome(
        data=stop_running_app(params["pid"], params["port"], params["started_at"])
    )


def _docker_start_prepare(params: dict, _state) -> dict:
    container = find_docker_container(params["container_id"], params["expected_state"])
    return {
        "summary": f"Start Docker container {container['name']}",
        "commands": [f"docker container start {container['container_id'][:12]}"],
        "files_changed": [],
        "scopes": ["services", "docker", container["container_id"]],
        "backup": None,
        "removals": [],
    }


def _docker_start_execute(params: dict, _state) -> ActionOutcome:
    return ActionOutcome(
        data=start_docker_container(params["container_id"], params["expected_state"])
    )


def _docker_stop_prepare(params: dict, _state) -> dict:
    container = find_docker_container(params["container_id"], params["expected_state"])
    return {
        "summary": f"Stop Docker container {container['name']}",
        "commands": [f"docker container stop --time 10 {container['container_id'][:12]}"],
        "files_changed": [],
        "scopes": ["services", "docker", container["container_id"]],
        "backup": "Start the same Docker container again to recover",
        "removals": [f"Running container {container['name']} ({container['container_id'][:12]})"],
    }


def _docker_stop_execute(params: dict, _state) -> ActionOutcome:
    return ActionOutcome(
        data=stop_docker_container(params["container_id"], params["expected_state"])
    )


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
    params_schema=_SERVICE_SCHEMA,
    prepare=_setup_prepare,
    execute=_setup_execute,
    compute_digest=lambda params, _state: services_digest(params["key"]),
)

SERVICES_START_DESCRIPTOR = ActionDescriptor(
    action_id="services.start",
    module="services",
    destructive=False,
    params_schema=_SERVICE_SCHEMA,
    prepare=_start_prepare,
    execute=_start_execute,
    compute_digest=lambda params, _state: services_digest(params["key"]),
)

SERVICES_STOP_DESCRIPTOR = ActionDescriptor(
    action_id="services.stop",
    module="services",
    destructive=True,
    params_schema=_SERVICE_SCHEMA,
    prepare=_stop_prepare,
    execute=_stop_execute,
    compute_digest=lambda params, _state: services_digest(params["key"]),
)

SERVICES_DASHBOARD_DESCRIPTOR = ActionDescriptor(
    action_id="services.dashboard",
    module="services",
    destructive=False,
    params_schema=_SERVICE_SCHEMA,
    prepare=_dashboard_prepare,
    execute=_dashboard_execute,
    compute_digest=lambda params, _state: services_digest(params["key"]),
)

RUNNING_APP_STOP_DESCRIPTOR = ActionDescriptor(
    action_id="services.running_app.stop",
    module="services",
    destructive=True,
    params_schema=_RUNNING_APP_SCHEMA,
    prepare=_running_app_stop_prepare,
    execute=_running_app_stop_execute,
    compute_digest=lambda params, _state: running_app_digest(
        params["pid"], params["port"], params["started_at"]
    ),
)

DOCKER_START_DESCRIPTOR = ActionDescriptor(
    action_id="services.docker.start",
    module="services",
    destructive=False,
    params_schema=_DOCKER_CONTAINER_SCHEMA,
    prepare=_docker_start_prepare,
    execute=_docker_start_execute,
    compute_digest=lambda params, _state: docker_container_digest(
        params["container_id"], params["expected_state"]
    ),
)

DOCKER_STOP_DESCRIPTOR = ActionDescriptor(
    action_id="services.docker.stop",
    module="services",
    destructive=True,
    params_schema=_DOCKER_CONTAINER_SCHEMA,
    prepare=_docker_stop_prepare,
    execute=_docker_stop_execute,
    compute_digest=lambda params, _state: docker_container_digest(
        params["container_id"], params["expected_state"]
    ),
)

SERVICES_DESCRIPTORS = (
    SERVICES_SETUP_DESCRIPTOR,
    SERVICES_START_DESCRIPTOR,
    SERVICES_STOP_DESCRIPTOR,
    SERVICES_DASHBOARD_DESCRIPTOR,
    RUNNING_APP_STOP_DESCRIPTOR,
    DOCKER_START_DESCRIPTOR,
    DOCKER_STOP_DESCRIPTOR,
)
