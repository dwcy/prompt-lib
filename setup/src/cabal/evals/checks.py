# -*- coding: utf-8 -*-
"""Deterministic check execution: run a task's CheckSpecs in the worktree, parse outcomes.

Per research.md R10: each check is an argv subprocess (never a shell) with its own timeout;
`pytest`/`dotnet` parsers extract passed/failed counts from the output tail, everything else
falls back to exit-code semantics. A check outcome — including a timeout — is recorded data,
never an exception: `run_checks` cannot abort the cell that called it.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cabal.evals.definitions_model import CheckSpec, Task
from cabal.evals.proc import kill_process_tree

OUTPUT_TAIL_CHARS: Final[int] = 4000

_PYTEST_PASSED: Final[re.Pattern[str]] = re.compile(r"(\d+) passed")
_PYTEST_FAILED: Final[re.Pattern[str]] = re.compile(r"(\d+) failed")
_DOTNET_PASSED: Final[re.Pattern[str]] = re.compile(r"Passed:\s*(\d+)")
_DOTNET_FAILED: Final[re.Pattern[str]] = re.compile(r"Failed:\s*(\d+)")


@dataclass(frozen=True)
class CheckResult:
    """One executed check, field-for-field the metrics.schema.json `$defs.check_result` shape."""

    kind: str
    cmd: list[str]
    status: str
    exit_code: int | None
    passed_count: int | None
    failed_count: int | None
    duration_seconds: float


def _parse_pytest(tail: str) -> tuple[int | None, int | None]:
    """pytest omits zero-count categories from its summary, so one found match implies the other is 0."""
    passed = _PYTEST_PASSED.findall(tail)
    failed = _PYTEST_FAILED.findall(tail)
    if not passed and not failed:
        return None, None
    return int(passed[-1]) if passed else 0, int(failed[-1]) if failed else 0


def _parse_dotnet(tail: str) -> tuple[int | None, int | None]:
    """`dotnet test` prints one `Passed!`/`Failed!` summary line per test project; counts sum across them."""
    passed = _DOTNET_PASSED.findall(tail)
    failed = _DOTNET_FAILED.findall(tail)
    if not passed and not failed:
        return None, None
    return sum(int(n) for n in passed), sum(int(n) for n in failed)


def _parse_counts(parser: str, output: str) -> tuple[int | None, int | None]:
    tail = output[-OUTPUT_TAIL_CHARS:]
    if parser == "pytest":
        return _parse_pytest(tail)
    if parser == "dotnet":
        return _parse_dotnet(tail)
    return None, None


def _status(exit_code: int, failed_count: int | None) -> str:
    """Counts refine exit-code semantics but never contradict a nonzero exit into `passed`."""
    if failed_count is not None:
        return "passed" if failed_count == 0 and exit_code == 0 else "failed"
    return "passed" if exit_code == 0 else "failed"


def _run_check(spec: CheckSpec, worktree: Path, default_timeout: int) -> CheckResult:
    timeout = spec.timeout_seconds if spec.timeout_seconds is not None else default_timeout
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            spec.cmd,
            cwd=worktree,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=(sys.platform != "win32"),
        )
    except OSError:
        return CheckResult(
            kind=spec.kind,
            cmd=list(spec.cmd),
            status="error",
            exit_code=None,
            passed_count=None,
            failed_count=None,
            duration_seconds=round(time.monotonic() - started, 3),
        )
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_process_tree(process)
        process.communicate()
        return CheckResult(
            kind=spec.kind,
            cmd=list(spec.cmd),
            status="timeout",
            exit_code=None,
            passed_count=None,
            failed_count=None,
            duration_seconds=round(time.monotonic() - started, 3),
        )
    duration = round(time.monotonic() - started, 3)
    passed_count, failed_count = _parse_counts(spec.parser, output or "")
    return CheckResult(
        kind=spec.kind,
        cmd=list(spec.cmd),
        status=_status(process.returncode, failed_count),
        exit_code=process.returncode,
        passed_count=passed_count,
        failed_count=failed_count,
        duration_seconds=duration,
    )


def run_checks(task: Task, worktree: Path, default_timeout: int) -> list[CheckResult]:
    """Execute every declared check in order with cwd = the run's worktree; never raises."""
    return [_run_check(spec, Path(worktree), default_timeout) for spec in task.checks]
