# -*- coding: utf-8 -*-
"""Session-scoped supervisor for local agent services: status, start, and stop (subprocess I/O)."""

from __future__ import annotations

import platform
import shutil
import socket
import subprocess

from cabal import service_prereqs
from cabal.service_catalog import (
    ServiceDefinition,
    ServiceState,
    ServiceStatus,
    all_services,
    get_service,
)
from cabal.service_prereqs import is_set_up

_PROBE_HOST = "127.0.0.1"
_PROBE_TIMEOUT = 0.25

_INFO_DETAIL = "client-launched MCP server"

_DEFAULT_AGENT = "claude"
_STOP_GRACE_SECONDS = 3.0

# Per-service spawn command tail appended to the resolved console executable.
_RUN_ARGS: dict[str, tuple[str, ...]] = {
    "a2a-bridge": ("serve", _DEFAULT_AGENT),
    "orchestrator": ("serve",),
}

# Session-scoped runtime state. _PROCS holds processes this session spawned;
# liveness reconciles a tracked PID's exit and falls back to a port probe.
_STATES: dict[str, ServiceState] = {}
_PROCS: dict[str, subprocess.Popen] = {}


def status(key: str) -> ServiceState:
    return reconcile(key)


def statuses() -> dict[str, ServiceState]:
    return {service.key: reconcile(service.key) for service in all_services()}


def reconcile(key: str) -> ServiceState:
    """Re-probe liveness and return the corrected, never-stale state."""
    definition = get_service(key)
    state = _STATES.setdefault(key, ServiceState(key=key, status=ServiceStatus.STOPPED))

    if not definition.runnable:
        state.status = ServiceStatus.INFO_ONLY
        state.detail = _INFO_DETAIL
        return state

    if not is_set_up(key):
        _clear_proc(key, state)
        state.status = ServiceStatus.NOT_SET_UP
        return state

    if _proc_alive(key):
        state.status = ServiceStatus.RUNNING
        return state

    # A tracked process that has exited must not leave a stale RUNNING/pid.
    _clear_proc(key, state)

    if _port_running(definition):
        state.status = ServiceStatus.RUNNING
        state.detail = f"port {definition.default_port} open"
        return state

    if state.status not in (ServiceStatus.BLOCKED,):
        state.status = ServiceStatus.STOPPED
        state.detail = ""
    return state


def start(key: str) -> ServiceState:
    """Start a runnable service after prereqs pass; otherwise return a non-RUNNING state.

    INFO_ONLY (mcp-bus) and NOT_SET_UP services never spawn. Unmet prerequisites
    yield BLOCKED with the joined messages and no spawn. A spawn failure yields
    BLOCKED with the OSError detail.
    """
    definition = get_service(key)
    state = _STATES.setdefault(key, ServiceState(key=key, status=ServiceStatus.STOPPED))

    if not definition.runnable:
        state.status = ServiceStatus.INFO_ONLY
        state.detail = _INFO_DETAIL
        return state

    if not is_set_up(key):
        _clear_proc(key, state)
        state.status = ServiceStatus.NOT_SET_UP
        state.detail = f"{definition.console_name} not found on PATH; set it up first."
        return state

    if _proc_alive(key) or _port_running(definition):
        return reconcile(key)

    unmet = service_prereqs.blocking(service_prereqs.check(key))
    if unmet:
        state.status = ServiceStatus.BLOCKED
        state.detail = " ".join(result.message for result in unmet if result.message)
        return state

    return _spawn(definition, state)


def open_dashboard(key: str) -> tuple[list[str] | None, str]:
    """Resolve the foreground argv for a service's native dashboard.

    Returns (argv, message). argv is None when the service has no dashboard or
    its console command is not yet on PATH; the message is then actionable. The
    caller runs the argv inside `App.suspend()` — this resolves it, it does not
    spawn it.
    """
    definition = get_service(key)
    command = definition.dashboard_command
    if not command:
        return None, f"{definition.label} has no native dashboard."
    parts = command.split()
    executable = shutil.which(parts[0])
    if executable is None:
        return None, (f"{parts[0]} is not on PATH — set up {definition.label} first.")
    return [executable, *parts[1:]], f"Opening {command}…"


def stop(key: str) -> ServiceState:
    """Stop a service this session started; a no-op for anything not tracked-and-alive."""
    definition = get_service(key)
    state = _STATES.setdefault(key, ServiceState(key=key, status=ServiceStatus.STOPPED))

    if not definition.runnable:
        state.status = ServiceStatus.INFO_ONLY
        state.detail = _INFO_DETAIL
        return state

    proc = _PROCS.get(key)
    if proc is None or proc.poll() is not None:
        return reconcile(key)

    _terminate(proc)
    _PROCS.pop(key, None)
    state.pid = None
    state.started_by_cabal = False
    state.status = ServiceStatus.STOPPED
    state.detail = ""
    return state


def _spawn(definition: ServiceDefinition, state: ServiceState) -> ServiceState:
    executable = shutil.which(definition.console_name) or definition.console_name
    command = [executable, *_RUN_ARGS.get(definition.key, ())]
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            **_detach_kwargs(),
        )
    except OSError as exc:
        state.status = ServiceStatus.BLOCKED
        state.detail = f"Could not start {definition.console_name}: {exc}"
        return state

    _PROCS[definition.key] = proc
    state.status = ServiceStatus.RUNNING
    state.pid = proc.pid
    state.started_by_cabal = True
    state.detail = f"pid {proc.pid}"
    return state


def _detach_kwargs() -> dict[str, object]:
    """Spawn the child detached so the daemon outlives the cabal session."""
    if platform.system() == "Windows":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        return {"creationflags": flags}
    return {"start_new_session": True}


def _terminate(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
    except OSError:
        return
    try:
        proc.wait(timeout=_STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            return
        try:
            proc.wait(timeout=_STOP_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass


def _proc_alive(key: str) -> bool:
    proc = _PROCS.get(key)
    return proc is not None and proc.poll() is None


def _clear_proc(key: str, state: ServiceState) -> None:
    proc = _PROCS.get(key)
    if proc is not None and proc.poll() is not None:
        _PROCS.pop(key, None)
        state.pid = None
        state.started_by_cabal = False


def _port_running(definition: ServiceDefinition) -> bool:
    return definition.default_port is not None and _port_open(definition.default_port)


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(_PROBE_TIMEOUT)
        return sock.connect_ex((_PROBE_HOST, port)) == 0
