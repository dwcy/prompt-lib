"""Unit tests for cabal.service_supervisor — the C3 start/stop/reconcile state machine (T012).

Drives the supervisor with a real long-running child (a Python sleeper) swapped in
for the real service binary via monkeypatched command-resolution seams, so the
state transitions (RUNNING / STOPPED / BLOCKED / NOT_SET_UP / INFO_ONLY) are
exercised against actual process liveness without depending on installed services.
"""

from __future__ import annotations

import sys
import time
from typing import Iterator

import pytest

from cabal import service_prereqs, service_supervisor
from cabal.service_catalog import PrereqResult, ServiceStatus, get_service

_A2A_TOKEN_ENV = "A2A_BEARER_TOKEN"

_SLEEPER_ARGS = ("-c", "import time; time.sleep(30)")
_POLL_TIMEOUT = 5.0
_POLL_INTERVAL = 0.02


@pytest.fixture(autouse=True)
def reset_supervisor_state() -> Iterator[None]:
    """Isolate each test: clear module state up front, kill any tracked child after."""
    service_supervisor._STATES.clear()
    service_supervisor._PROCS.clear()
    try:
        yield
    finally:
        for proc in list(service_supervisor._PROCS.values()):
            try:
                proc.kill()
                proc.wait(timeout=_POLL_TIMEOUT)
            except (OSError, Exception):
                pass
        service_supervisor._PROCS.clear()
        service_supervisor._STATES.clear()


@pytest.fixture
def sleeper_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make start() spawn a real Python sleeper instead of the service binary.

    Seams patched:
      - service_supervisor.shutil.which -> sys.executable (resolves the "binary")
      - service_supervisor._RUN_ARGS    -> sleeper argv tail
      - service_supervisor.is_set_up    -> True (PATH presence satisfied)
      - service_supervisor._port_open   -> False (no stray port masks STOPPED)
      - service_prereqs.check           -> [] (no unmet prerequisites)
    """
    monkeypatch.setattr(service_supervisor.shutil, "which", lambda _name: sys.executable)
    monkeypatch.setattr(
        service_supervisor,
        "_RUN_ARGS",
        {"a2a-bridge": _SLEEPER_ARGS, "orchestrator": _SLEEPER_ARGS},
    )
    monkeypatch.setattr(service_supervisor, "is_set_up", lambda _key: True)
    monkeypatch.setattr(service_supervisor, "_port_open", lambda _port: False)
    monkeypatch.setattr(service_prereqs, "check", lambda _key: [])


def _wait_until(predicate, timeout: float = _POLL_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(_POLL_INTERVAL)
    return predicate()


# ------------------------------------------------------------------
# 1. start happy path -> RUNNING, then stop -> STOPPED
# ------------------------------------------------------------------


def test_start_spawns_a_live_child_and_marks_running(sleeper_spawn):
    state = service_supervisor.start("a2a-bridge")

    assert state.status is ServiceStatus.RUNNING
    assert state.started_by_cabal is True
    proc = service_supervisor._PROCS["a2a-bridge"]
    assert proc.pid == state.pid
    assert proc.poll() is None


def test_status_after_start_reports_running(sleeper_spawn):
    service_supervisor.start("a2a-bridge")

    assert service_supervisor.status("a2a-bridge").status is ServiceStatus.RUNNING


def test_stop_terminates_the_child_and_marks_stopped(sleeper_spawn):
    service_supervisor.start("a2a-bridge")
    proc = service_supervisor._PROCS["a2a-bridge"]

    state = service_supervisor.stop("a2a-bridge")

    assert state.status is ServiceStatus.STOPPED
    assert _wait_until(lambda: proc.poll() is not None)
    assert "a2a-bridge" not in service_supervisor._PROCS


# ------------------------------------------------------------------
# 2. external exit -> reconcile -> STOPPED (no stale RUNNING)
# ------------------------------------------------------------------


def test_external_exit_reconciles_to_stopped(sleeper_spawn):
    service_supervisor.start("a2a-bridge")
    proc = service_supervisor._PROCS["a2a-bridge"]

    proc.kill()
    assert _wait_until(lambda: proc.poll() is not None)

    assert service_supervisor.status("a2a-bridge").status is ServiceStatus.STOPPED


def test_reconcile_clears_tracked_proc_after_external_exit(sleeper_spawn):
    service_supervisor.start("a2a-bridge")
    proc = service_supervisor._PROCS["a2a-bridge"]
    proc.kill()
    assert _wait_until(lambda: proc.poll() is not None)

    service_supervisor.reconcile("a2a-bridge")

    assert "a2a-bridge" not in service_supervisor._PROCS


# ------------------------------------------------------------------
# 3. prereq fail -> BLOCKED, no spawn
# ------------------------------------------------------------------


def test_prereq_failure_returns_blocked_without_spawning(monkeypatch):
    monkeypatch.setattr(service_supervisor, "is_set_up", lambda _key: True)
    monkeypatch.setattr(service_supervisor, "_port_open", lambda _port: False)
    failing = PrereqResult(name="A2A_BEARER_TOKEN", ok=False, message="token missing")
    monkeypatch.setattr(service_prereqs, "check", lambda _key: [failing])

    state = service_supervisor.start("a2a-bridge")

    assert state.status is ServiceStatus.BLOCKED
    assert "token missing" in state.detail
    assert "a2a-bridge" not in service_supervisor._PROCS


# ------------------------------------------------------------------
# 4. not set up -> NOT_SET_UP, no spawn
# ------------------------------------------------------------------


def test_not_set_up_returns_not_set_up_without_spawning(monkeypatch):
    monkeypatch.setattr(service_supervisor, "is_set_up", lambda _key: False)

    state = service_supervisor.start("a2a-bridge")

    assert state.status is ServiceStatus.NOT_SET_UP
    assert "a2a-bridge" not in service_supervisor._PROCS


# ------------------------------------------------------------------
# 6. stop when nothing running -> reconciled no-op, never raises
# ------------------------------------------------------------------


def test_stop_untracked_service_is_a_noop(monkeypatch):
    monkeypatch.setattr(service_supervisor, "is_set_up", lambda _key: True)
    monkeypatch.setattr(service_supervisor, "_port_open", lambda _port: False)

    state = service_supervisor.stop("a2a-bridge")

    assert state.status is ServiceStatus.STOPPED
    assert "a2a-bridge" not in service_supervisor._PROCS


# ------------------------------------------------------------------
# 7. A2A bearer token: cabal auto-provisions one shared session token
# ------------------------------------------------------------------


def test_child_env_injects_session_token_when_unset(monkeypatch):
    monkeypatch.delenv(_A2A_TOKEN_ENV, raising=False)
    monkeypatch.setattr(service_supervisor, "_SESSION_BEARER_TOKEN", None)

    env = service_supervisor._child_env(get_service("a2a-bridge"))

    assert env is not None
    assert env[_A2A_TOKEN_ENV]


def test_child_env_shares_one_token_across_token_services(monkeypatch):
    monkeypatch.delenv(_A2A_TOKEN_ENV, raising=False)
    monkeypatch.setattr(service_supervisor, "_SESSION_BEARER_TOKEN", None)

    bridge_env = service_supervisor._child_env(get_service("a2a-bridge"))
    orch_env = service_supervisor._child_env(get_service("orchestrator"))

    assert bridge_env[_A2A_TOKEN_ENV] == orch_env[_A2A_TOKEN_ENV]


def test_child_env_respects_a_user_supplied_token(monkeypatch):
    monkeypatch.setenv(_A2A_TOKEN_ENV, "user-secret")

    env = service_supervisor._child_env(get_service("a2a-bridge"))

    assert env[_A2A_TOKEN_ENV] == "user-secret"
