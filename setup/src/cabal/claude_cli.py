# -*- coding: utf-8 -*-
"""Shared subprocess wrappers for the `claude` CLI with MSYS path-conv shim."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class ClaudeRunResult:
    returncode: int
    stdout: str
    stderr: str
    cancelled: bool = False


def _run_claude_cli(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a `claude` CLI command with MSYS path conversion disabled (Git Bash safety)."""
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    try:
        r = subprocess.run(["claude", *args], capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", "claude CLI not found in PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    except Exception as e:
        return 1, "", str(e)


def spawn_claude(
    args: list[str],
    cwd: Path | str,
    env_extra: dict[str, str] | None = None,
) -> subprocess.Popen:
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    if env_extra:
        env.update(env_extra)
    return subprocess.Popen(
        ["claude", *args],
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def claude_print(
    prompt: str,
    cwd: Path | str,
    on_line: Callable[[str], None] | None = None,
    timeout: float | None = None,
) -> ClaudeRunResult:
    """Run `claude -p <prompt>` streaming stdout via on_line; returns ClaudeRunResult."""
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    try:
        proc = subprocess.Popen(
            ["claude", "-p", prompt],
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return ClaudeRunResult(returncode=127, stdout="", stderr="claude CLI not found in PATH")
    except Exception as e:
        return ClaudeRunResult(returncode=1, stdout="", stderr=str(e))

    accumulated: list[str] = []
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            accumulated.append(line)
            stripped = line.strip()
            if stripped and on_line is not None:
                on_line(stripped)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            return ClaudeRunResult(
                returncode=124,
                stdout="\n".join(accumulated),
                stderr="timed out",
                cancelled=True,
            )
        err = proc.stderr.read() if proc.stderr is not None else ""
        return ClaudeRunResult(returncode=proc.returncode, stdout="\n".join(accumulated), stderr=err)
    except Exception as e:
        try:
            proc.kill()
        except Exception:
            pass
        return ClaudeRunResult(returncode=1, stdout="\n".join(accumulated), stderr=str(e))
