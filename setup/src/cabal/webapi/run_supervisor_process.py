# -*- coding: utf-8 -*-
"""Cross-platform detached-process spawn/kill primitives backing `run_supervisor.py`.

Isolated from `run_supervisor.py`'s domain logic (reconciliation, module availability)
because "how do I start a process that outlives this one, and kill one found again
later by bare pid alone" is a distinct concern from "what does a supervised codegen/evals
run's state mean" -- this module has no knowledge of either subsystem.

Per research.md R1, the process this spawns must survive both a normal backend restart
and the Tauri shell's `RunEvent::Exit` handler, which kills only the specific backend pid
it spawned (`apps/cabal-desktop/src-tauri/src/backend.rs::shutdown`, `child.kill()`) --
not a process-group or job-object sweep of the whole tree, as far as this backend can
observe from the child's side. Windows sidecar tooling commonly wraps a spawned child in
a Job Object with kill-on-close specifically so orphaned grandchildren do not survive the
app closing; if this backend's own process happens to be inside such a job, an ordinary
child of it would inherit that membership and die alongside it. `CREATE_BREAKAWAY_FROM_JOB`
is the documented escape hatch, applied best-effort: some job policies refuse breakaway
(`ERROR_ACCESS_DENIED`), so a plain detached spawn is the fallback rather than a hard
failure. POSIX needs no such workaround: `start_new_session=True` (`setsid`) moves the
child to its own session and process group, so a group-directed signal at the backend's
own group never reaches it.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from cabal.evals.proc import kill_process_tree
from cabal.webapi.security import is_pid_alive

if sys.platform == "win32":
    _CREATE_BREAKAWAY_FROM_JOB = 0x01000000
    _DETACHED_FLAGS = (
        subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.DETACHED_PROCESS
        | _CREATE_BREAKAWAY_FROM_JOB
    )
    _DETACHED_FLAGS_NO_BREAKAWAY = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS


def spawn_detached(
    command: Sequence[str],
    *,
    cwd: Path | str,
    env: Mapping[str, str] | None = None,
    log_path: Path | None = None,
) -> subprocess.Popen[str]:
    """Spawn `command` so it keeps running after this backend process exits."""
    stdio = _log_stream(log_path)
    kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "env": dict(env) if env is not None else None,
        "stdin": subprocess.DEVNULL,
        "stdout": stdio,
        "stderr": stdio,
        "text": True,
        "close_fds": True,
    }
    if sys.platform == "win32":
        try:
            return subprocess.Popen(list(command), creationflags=_DETACHED_FLAGS, **kwargs)
        except OSError:
            return subprocess.Popen(
                list(command), creationflags=_DETACHED_FLAGS_NO_BREAKAWAY, **kwargs
            )
    return subprocess.Popen(list(command), start_new_session=True, **kwargs)


def _log_stream(log_path: Path | None) -> int | object:
    if log_path is None:
        return subprocess.DEVNULL
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return open(log_path, "a", encoding="utf-8")  # noqa: SIM115 -- owned by the child for its lifetime


class _PidHandle:
    """Duck-types the slice of `subprocess.Popen` that `kill_process_tree` calls
    (`.pid`, `.poll()`, `.kill()`), so a bare `pid` recovered after a backend restart --
    `SupervisedRun`'s only durable field, per data-model B1 -- can reuse the exact same
    cross-platform tree-kill a live handle would use. No live `Popen` object survives a
    restart by design (research.md R1/R2), so this is the only way to reuse it there.
    """

    def __init__(self, pid: int) -> None:
        self.pid = pid

    def poll(self) -> int | None:
        return None if is_pid_alive(self.pid) else 0

    def kill(self) -> None:
        # win32: kill_process_tree's `taskkill /T /F /PID` already covers the root.
        if sys.platform != "win32":
            try:
                os.kill(self.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def terminate_by_pid(pid: int) -> None:
    """Kill a run's whole process tree, found again by bare pid alone (research.md R1/T013)."""
    kill_process_tree(_PidHandle(pid))
