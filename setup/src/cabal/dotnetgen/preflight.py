# -*- coding: utf-8 -*-
"""Toolchain preflight: verify the .NET SDK and Python interpreter the pipeline depends on.

Runs before any model is called. A toolchain problem found here is an environment failure,
not a code defect, and per FR-022 it must never consume the repair budget.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

MIN_DOTNET_MAJOR = 10
MIN_PYTHON = (3, 14)

_SDK_LINE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True)
class ToolchainReport:
    """Outcome of a preflight run. `ok` is the only field callers must branch on."""

    ok: bool
    python_version: str
    dotnet_path: str | None
    dotnet_sdks: tuple[str, ...] = ()
    selected_sdk: str | None = None
    problems: tuple[str, ...] = field(default=())

    def summary(self) -> str:
        if self.ok:
            return f"python {self.python_version}, .NET SDK {self.selected_sdk}"
        return "; ".join(self.problems)


def _python_problem() -> str | None:
    if sys.version_info < MIN_PYTHON:
        want = ".".join(str(p) for p in MIN_PYTHON)
        return f"Python {want}+ required, found {sys.version.split()[0]}"
    return None


def _list_sdks(dotnet: str) -> tuple[tuple[str, ...], str | None]:
    """Return every installed SDK version and the highest one meeting MIN_DOTNET_MAJOR."""
    try:
        proc = subprocess.run(
            [dotnet, "--list-sdks"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return (), None

    versions: list[tuple[tuple[int, int, int], str]] = []
    for line in proc.stdout.splitlines():
        match = _SDK_LINE.match(line.strip())
        if match is None:
            continue
        parts = tuple(int(g) for g in match.groups())
        versions.append((parts, match.group(0)))

    versions.sort()
    eligible = [text for parts, text in versions if parts[0] >= MIN_DOTNET_MAJOR]
    return tuple(text for _, text in versions), (eligible[-1] if eligible else None)


def check() -> ToolchainReport:
    """Inspect the local toolchain without mutating anything."""
    problems: list[str] = []
    python_version = sys.version.split()[0]

    problem = _python_problem()
    if problem is not None:
        problems.append(problem)

    dotnet = shutil.which("dotnet")
    if dotnet is None:
        problems.append("`dotnet` not found on PATH - install the .NET SDK")
        return ToolchainReport(
            ok=False,
            python_version=python_version,
            dotnet_path=None,
            problems=tuple(problems),
        )

    sdks, selected = _list_sdks(dotnet)
    if not sdks:
        problems.append("`dotnet --list-sdks` reported no SDKs")
    elif selected is None:
        problems.append(
            f".NET SDK {MIN_DOTNET_MAJOR}.x required, found only: {', '.join(sdks)}"
        )

    return ToolchainReport(
        ok=not problems,
        python_version=python_version,
        dotnet_path=dotnet,
        dotnet_sdks=sdks,
        selected_sdk=selected,
        problems=tuple(problems),
    )
