#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Process-tree and handshake ownership for the dev backend supervisor: who currently holds the
port, how to stop them, and when the handshake file is safe to delete.

Returns messages rather than printing them, so the supervisor owns all console output.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import platformdirs
import psutil

# A process is only ever killed when its command line names one of these.
BACKEND_MARKERS = ("cabal-backend", "cabal.webapi")


def default_handshake_path() -> Path:
    return Path(platformdirs.user_data_dir("cabal", appauthor=False)) / "webapi-handshake.json"


def _family_of(process: psutil.Process) -> list[psutil.Process]:
    try:
        return [*process.children(recursive=True), process]
    except psutil.NoSuchProcess:
        return []


def terminate_family(family: Sequence[psutil.Process]) -> None:
    """Ask a process group to exit, then hard-kill whatever is still alive."""
    for member in family:
        try:
            member.terminate()
        except psutil.NoSuchProcess:
            continue
    _, alive = psutil.wait_procs(list(family), timeout=5)
    for member in alive:
        try:
            member.kill()
        except psutil.NoSuchProcess:
            continue


def kill_tree(process: subprocess.Popen[str]) -> str | None:
    """Terminate the child and every descendant. Returns a warning if it would not die."""
    if process.poll() is not None:
        return None
    try:
        family = _family_of(psutil.Process(process.pid))
    except psutil.NoSuchProcess:
        return None
    terminate_family(family)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return "warning: backend did not exit cleanly"
    return None


def looks_like_backend(process: psutil.Process) -> bool:
    """True only when the command line actually names the cabal backend.

    The handshake records a pid and pids get recycled, so by the time we read one an unrelated
    process may be sitting on that number. Never kill on the strength of a pid alone.
    """
    try:
        cmdline = " ".join(process.cmdline()).lower()
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return False
    return any(marker in cmdline for marker in BACKEND_MARKERS)


def read_handshake(handshake_path: Path) -> dict | None:
    try:
        data = json.loads(handshake_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def clear_stale_handshake(handshake_path: Path) -> None:
    """Remove the handshake only when the process that wrote it is gone.

    A hard kill on Windows skips the backend's own cleanup, so a dead instance's file lingers and
    the supervisor would read it and announce the previous port for the new process. A *live*
    owner's file must be left exactly where it is: cabal-backend reads it to refuse a second
    start, and deleting it would let the supervisor start a rival backend behind a running app.
    """
    data = read_handshake(handshake_path)
    if data is None:
        return
    pid = data.get("pid")
    if isinstance(pid, int) and psutil.pid_exists(pid):
        return
    try:
        handshake_path.unlink()
    except OSError:
        pass


def takeover(handshake_path: Path) -> tuple[bool, str | None]:
    """Stop the backend currently holding the handshake so a fresh one can own the port.

    cabal-backend refuses to start while another instance is live. That is right for the
    packaged app, but in a dev loop the live instance is precisely the stale code you are
    replacing. Returns (stopped, message-to-log).
    """
    data = read_handshake(handshake_path)
    if data is None or not isinstance(data.get("pid"), int):
        return False, None
    pid = data["pid"]
    try:
        existing = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return False, None
    if not looks_like_backend(existing):
        return False, f"handshake pid {pid} is not a cabal backend ({existing.name()}); leaving it alone"

    message = f"stopping the backend already on port {data.get('port')} (pid {pid})"
    terminate_family(_family_of(existing))
    clear_stale_handshake(handshake_path)
    return True, message
