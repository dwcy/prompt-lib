# -*- coding: utf-8 -*-
"""Session-scoped supervisor for local agent services: status, start, and stop (subprocess I/O)."""

from __future__ import annotations

import os
import platform
import secrets
import shutil
import socket
import subprocess
from pathlib import Path
from typing import TextIO

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

# Captured stdout/stderr of cabal-spawned services lands here, one file per key,
# so the Services log view can tail a run and the last run survives cabal exit.
_LOG_DIR = Path.home() / ".cabal" / "logs"
_LOG_SUFFIX = ".log"

_A2A_TOKEN_ENV = "A2A_BEARER_TOKEN"
# Services that speak the A2A bearer-token handshake (bridge auth + orchestrator delegation).
_TOKEN_SERVICES = ("a2a-bridge", "orchestrator")

# Per-service spawn command tail appended to the resolved console executable.
_RUN_ARGS: dict[str, tuple[str, ...]] = {
    "a2a-bridge": ("serve", _DEFAULT_AGENT),
    "orchestrator": ("serve",),
}

# Session-scoped runtime state. _PROCS holds processes this session spawned;
# liveness reconciles a tracked PID's exit and falls back to a port probe.
_STATES: dict[str, ServiceState] = {}
_PROCS: dict[str, subprocess.Popen] = {}
# Open log file handles for live-captured services, closed on stop / proc clear.
_LOGS: dict[str, TextIO] = {}

# One ephemeral A2A bearer token shared by every service cabal starts this session.
_SESSION_BEARER_TOKEN: str | None = None


def _session_bearer_token() -> str:
    """Return one strong ephemeral A2A bearer token per cabal session.

    Lets cabal start a2a-bridge + orchestrator on loopback with no manual
    A2A_BEARER_TOKEN: both children share this secret, so the bridge's auth stays
    enforced and the orchestrator still authenticates when it delegates.
    """
    global _SESSION_BEARER_TOKEN
    if _SESSION_BEARER_TOKEN is None:
        _SESSION_BEARER_TOKEN = secrets.token_hex(32)
    return _SESSION_BEARER_TOKEN


def _child_env(definition: ServiceDefinition) -> dict[str, str] | None:
    """Child environment for a spawned service, auto-provisioning the shared A2A token.

    For the token-speaking services, when A2A_BEARER_TOKEN is unset cabal injects
    the session token so auth works without setup; a value the user already set is
    respected. Other services inherit the parent environment unchanged (None).
    """
    if definition.key not in _TOKEN_SERVICES:
        return None
    env = dict(os.environ)
    if not env.get(_A2A_TOKEN_ENV):
        env[_A2A_TOKEN_ENV] = _session_bearer_token()
    return env


def log_path(key: str) -> Path:
    """Deterministic capture-log path for a service; safe to call when it is stopped.

    Ensures the logs directory exists so the Services log view can always resolve a
    path, whether it is tailing a live run or showing the last run that already ended.
    """
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR / f"{key}{_LOG_SUFFIX}"


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
    _close_log(key)
    state.pid = None
    state.started_by_cabal = False
    state.status = ServiceStatus.STOPPED
    state.detail = ""
    return state


def shutdown_all() -> None:
    """Terminate every service this session started and close its log handle.

    Called on app exit so cabal never leaves an orphaned background process
    behind. Idempotent and exception-safe — safe to call from both the app's
    unmount hook and an atexit handler.
    """
    for key, proc in list(_PROCS.items()):
        try:
            if proc.poll() is None:
                _terminate(proc)
        except Exception:
            pass
        _PROCS.pop(key, None)
    for key in list(_LOGS):
        _close_log(key)
    for state in _STATES.values():
        if state.status == ServiceStatus.RUNNING:
            state.status = ServiceStatus.STOPPED
            state.pid = None
            state.started_by_cabal = False
            state.detail = ""


def _spawn(definition: ServiceDefinition, state: ServiceState) -> ServiceState:
    executable = shutil.which(definition.console_name) or definition.console_name
    command = [executable, *_RUN_ARGS.get(definition.key, ())]
    try:
        log = open(log_path(definition.key), "w", encoding="utf-8")
    except OSError as exc:
        state.status = ServiceStatus.BLOCKED
        state.detail = f"Could not open log for {definition.console_name}: {exc}"
        return state
    try:
        proc = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=_child_env(definition),
            **_detach_kwargs(),
        )
    except OSError as exc:
        log.close()
        state.status = ServiceStatus.BLOCKED
        state.detail = f"Could not start {definition.console_name}: {exc}"
        return state

    _PROCS[definition.key] = proc
    _LOGS[definition.key] = log
    state.status = ServiceStatus.RUNNING
    state.pid = proc.pid
    state.started_by_cabal = True
    state.detail = f"pid {proc.pid}"
    return state


def _detach_kwargs() -> dict[str, object]:
    """Spawn the child windowless-but-backgrounded so the daemon outlives cabal.

    Windows uses CREATE_NO_WINDOW (not DETACHED_PROCESS): DETACHED_PROCESS flashes a
    fresh console and drops our redirected stdout/stderr handles, so we lose the log.
    """
    if platform.system() == "Windows":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
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
        _close_log(key)
        state.pid = None
        state.started_by_cabal = False


def _close_log(key: str) -> None:
    log = _LOGS.pop(key, None)
    if log is not None:
        try:
            log.close()
        except OSError:
            pass


def _port_running(definition: ServiceDefinition) -> bool:
    return definition.default_port is not None and _port_open(definition.default_port)


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(_PROBE_TIMEOUT)
        return sock.connect_ex((_PROBE_HOST, port)) == 0
