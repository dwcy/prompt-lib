# -*- coding: utf-8 -*-
"""Unit tests for cabal.service_supervisor log capture: per-service log file + spawn flags.

Drives the supervisor with a real Python child that prints known text then sleeps, so
the captured log has deterministic content, and asserts the capture-file lifecycle
(open on start, closed on stop) plus the platform-specific detach flags — all hermetic
against a tmp_path log dir, never the user's ~/.cabal/logs.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

import pytest

from cabal import service_prereqs, service_supervisor
from cabal.service_catalog import ServiceStatus

_MARKER = "hello-from-service"
_PRINTER_ARGS = ("-c", f"print('{_MARKER}', flush=True); import time; time.sleep(30)")
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
        for log in list(service_supervisor._LOGS.values()):
            try:
                log.close()
            except OSError:
                pass
        service_supervisor._PROCS.clear()
        service_supervisor._LOGS.clear()
        service_supervisor._STATES.clear()


@pytest.fixture
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the supervisor's capture-log dir into tmp_path so nothing touches ~/.cabal."""
    target = tmp_path / "logs"
    monkeypatch.setattr(service_supervisor, "_LOG_DIR", target)
    return target


@pytest.fixture
def printer_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make start() spawn a real Python child that prints a marker then sleeps.

    Mirrors the sleeper_spawn seams from test_service_supervisor, but the child emits
    a known line to stdout so the captured log has assertable content.
    """
    monkeypatch.setattr(service_supervisor.shutil, "which", lambda _name: sys.executable)
    monkeypatch.setattr(
        service_supervisor,
        "_RUN_ARGS",
        {"a2a-bridge": _PRINTER_ARGS, "orchestrator": _PRINTER_ARGS},
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
# 1. log_path — deterministic path under the patched dir, dir created
# ------------------------------------------------------------------


def test_log_path_returns_path_under_patched_dir(log_dir: Path):
    path = service_supervisor.log_path("a2a-bridge")

    assert path == log_dir / "a2a-bridge.log"


def test_log_path_creates_the_log_directory(log_dir: Path):
    assert not log_dir.exists()

    service_supervisor.log_path("a2a-bridge")

    assert log_dir.is_dir()


def test_log_path_is_safe_when_nothing_is_running(log_dir: Path):
    first = service_supervisor.log_path("orchestrator")
    second = service_supervisor.log_path("orchestrator")

    assert first == second


# ------------------------------------------------------------------
# 2. capture on start — child stdout lands in the log file
# ------------------------------------------------------------------


def test_start_captures_child_stdout_to_the_log_file(log_dir, printer_spawn):
    state = service_supervisor.start("a2a-bridge")
    assert state.status is ServiceStatus.RUNNING

    path = service_supervisor.log_path("a2a-bridge")
    captured = _wait_until(
        lambda: path.is_file() and _MARKER in path.read_text(encoding="utf-8")
    )

    assert captured

    stopped = service_supervisor.stop("a2a-bridge")
    assert stopped.status is ServiceStatus.STOPPED


# ------------------------------------------------------------------
# 3. _close_log on stop — the tracked handle is dropped
# ------------------------------------------------------------------


def test_stop_closes_and_drops_the_log_handle(log_dir, printer_spawn):
    service_supervisor.start("a2a-bridge")
    assert "a2a-bridge" in service_supervisor._LOGS

    service_supervisor.stop("a2a-bridge")

    assert "a2a-bridge" not in service_supervisor._LOGS


def test_clear_proc_closes_log_after_external_exit(log_dir, printer_spawn):
    service_supervisor.start("a2a-bridge")
    proc = service_supervisor._PROCS["a2a-bridge"]
    proc.kill()
    assert _wait_until(lambda: proc.poll() is not None)

    service_supervisor.reconcile("a2a-bridge")

    assert "a2a-bridge" not in service_supervisor._LOGS


# ------------------------------------------------------------------
# 4. detach flags — windowless-but-backgrounded per platform
# ------------------------------------------------------------------


def test_windows_detach_flags_are_no_window_new_group(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service_supervisor.platform, "system", lambda: "Windows")
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    kwargs = service_supervisor._detach_kwargs()

    flags = kwargs["creationflags"]
    assert flags & no_window
    assert flags & new_group


def test_windows_detach_flags_exclude_detached_process(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service_supervisor.platform, "system", lambda: "Windows")
    detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)

    kwargs = service_supervisor._detach_kwargs()

    assert not (kwargs["creationflags"] & detached)


def test_posix_detach_kwargs_start_a_new_session(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service_supervisor.platform, "system", lambda: "Linux")

    kwargs = service_supervisor._detach_kwargs()

    assert kwargs == {"start_new_session": True}


# ------------------------------------------------------------------
# 5. shutdown_all — terminate every tracked child + close every log
# ------------------------------------------------------------------


def test_shutdown_all_terminates_children_and_closes_logs(log_dir, printer_spawn):
    service_supervisor.start("a2a-bridge")
    service_supervisor.start("orchestrator")
    procs = [
        service_supervisor._PROCS["a2a-bridge"],
        service_supervisor._PROCS["orchestrator"],
    ]
    assert all(proc.poll() is None for proc in procs)

    service_supervisor.shutdown_all()

    for proc in procs:
        assert _wait_until(lambda p=proc: p.poll() is not None)
    assert service_supervisor._PROCS == {}
    assert service_supervisor._LOGS == {}
    assert service_supervisor._STATES["a2a-bridge"].status is ServiceStatus.STOPPED


def test_shutdown_all_is_safe_when_nothing_started():
    service_supervisor.shutdown_all()
    service_supervisor.shutdown_all()

    assert service_supervisor._PROCS == {}
