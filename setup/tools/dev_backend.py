#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dev-only supervisor for `cabal-backend`: restarts it when Python sources change and labels
its output so backend activity is legible next to Vite's in one shared terminal.

Used by run-web / run-web.ps1. Packaged builds never run this — the Tauri shell spawns the
backend directly.

On startup it stops whatever backend is already holding the handshake and starts a fresh one:
cabal-backend's single-instance guard is right for the packaged app, but in a dev loop the live
instance is exactly the stale code you are replacing. `--no-takeover` restores the refusal.

Change detection lives in the sibling dev_watch module; this file owns the process lifecycle.

The whole process *tree* is killed on restart: `uv run` on Windows spawns the real interpreter
as a grandchild, so terminating our direct child would orphan the server still holding the port —
and the next start would then refuse with "another instance is already running".
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path

# Sibling modules: running this file as a script puts setup/tools on sys.path[0].
from dev_backend_procs import (
    clear_stale_handshake,
    default_handshake_path,
    kill_tree,
    takeover,
)
from dev_watch import changed_paths, describe, iter_watched_files, snapshot

POLL_SECONDS = 1.0
# One quiet interval after a change before restarting, so a multi-file save (or an editor's
# write-temp-then-rename) causes one restart rather than several.
DEBOUNCE_SECONDS = 0.4
HANDSHAKE_WAIT_SECONDS = 15.0


LABEL = "\033[36m[backend]\033[0m" if sys.stdout.isatty() else "[backend]"


def log(message: str) -> None:
    print(f"{LABEL} {message}", flush=True)


def _relay_output(process: subprocess.Popen[str]) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(f"{LABEL} {line.rstrip()}", flush=True)


def _report_handshake(handshake_path: Path, started_at: float) -> None:
    """Announce the port the backend actually bound, once its handshake appears."""
    deadline = time.monotonic() + HANDSHAKE_WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            data = json.loads(handshake_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.1)
            continue
        if isinstance(data, dict) and isinstance(data.get("port"), int):
            log(f"listening on 127.0.0.1:{data['port']} ({time.monotonic() - started_at:.1f}s)")
            return
        time.sleep(0.1)
    log("warning: no handshake appeared; the UI will show its disconnected state")


def launch(command: Sequence[str], cwd: Path, handshake_path: Path) -> subprocess.Popen[str]:
    """Start the backend and attach the output relay and the handshake watcher."""
    clear_stale_handshake(handshake_path)
    environment = dict(os.environ)
    # CABAL_DEV opens CORS to the Vite dev origins; packaged builds never set it.
    environment["CABAL_DEV"] = "1"
    # Without this the child block-buffers, so nothing appears until it exits.
    environment["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    threading.Thread(target=_relay_output, args=(process,), daemon=True).start()
    threading.Thread(
        target=_report_handshake, args=(handshake_path, time.monotonic()), daemon=True
    ).start()
    return process


def supervise(
    root: Path,
    watch_roots: Sequence[Path],
    command: Sequence[str],
    log_level: str,
    handshake_path: Path | None = None,
    claim: bool = True,
) -> int:
    handshake_path = handshake_path or default_handshake_path()
    if claim:
        _, notice = takeover(handshake_path)
        if notice:
            log(notice)
    full_command = [
        *command,
        "--project",
        str(root),
        "--log-level",
        log_level,
        "--handshake-path",
        str(handshake_path),
    ]

    stamps = snapshot(watch_roots)
    log(f"watching {len(stamps)} python files for changes")
    log(f"starting: {' '.join(full_command)}")
    process = launch(full_command, root, handshake_path)
    reported_exit = False

    try:
        while True:
            time.sleep(POLL_SECONDS)

            changes = changed_paths(stamps, snapshot(watch_roots))
            if changes:
                # Let a burst of writes settle, then re-read so one restart covers all of them.
                time.sleep(DEBOUNCE_SECONDS)
                current = snapshot(watch_roots)
                changes = changed_paths(stamps, current)
                stamps = current

                log(f"changed: {describe(changes, root)} -> restarting")
                warning = kill_tree(process)
                if warning:
                    log(warning)
                process = launch(full_command, root, handshake_path)
                reported_exit = False
                continue

            exit_code = process.poll()
            if exit_code is not None and not reported_exit:
                log(f"exited with code {exit_code}; edit a source file to retry")
                reported_exit = True
    except KeyboardInterrupt:
        log("stopping")
        return 0
    finally:
        kill_tree(process)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dev_backend",
        description="Restart cabal-backend when its Python sources change.",
    )
    parser.add_argument("--root", type=Path, default=None, help="Repository root (default: inferred)")
    parser.add_argument(
        "--log-level",
        default="info",
        help="Uvicorn log level passed through to cabal-backend (default: info)",
    )
    parser.add_argument(
        "--no-takeover",
        action="store_true",
        help="Refuse to start when another backend is live, instead of stopping it first",
    )
    parser.add_argument(
        "--handshake-path",
        type=Path,
        default=None,
        help="Handshake file to use; defaults to the shared per-user location",
    )
    args = parser.parse_args(argv)

    root = (args.root or Path(__file__).resolve().parents[2]).resolve()
    source_root = root / "setup" / "src" / "cabal"
    if not source_root.is_dir():
        print(f"dev_backend: no source tree at {source_root}", file=sys.stderr)
        return 2

    return supervise(
        root,
        [source_root],
        ["uv", "run", "cabal-backend"],
        args.log_level,
        args.handshake_path,
        claim=not args.no_takeover,
    )


if __name__ == "__main__":
    raise SystemExit(main())
