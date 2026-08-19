# -*- coding: utf-8 -*-
"""Cross-platform process-tree termination shared by agent adapters and deterministic checks."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Final

DEFAULT_GRACE_SECONDS: Final[int] = 30


def kill_process_tree(process: subprocess.Popen[str], grace_seconds: int = DEFAULT_GRACE_SECONDS) -> None:
    """Kill a process and all its descendants; a plain kill() would orphan spawned children.

    On win32 `taskkill /T /F` walks the tree; elsewhere the process was started in its own
    session (`start_new_session=True`) so the whole process group receives SIGKILL.
    """
    if process.poll() is None:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
                timeout=grace_seconds,
            )
        else:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
    try:
        process.kill()
    except OSError:
        pass
