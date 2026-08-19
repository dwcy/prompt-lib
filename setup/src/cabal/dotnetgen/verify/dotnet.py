# -*- coding: utf-8 -*-
"""Verification via the .NET toolchain: run `dotnet build`, then `dotnet test`, and capture the result.

This is the pipeline's feedback signal, and it is the component the frontend codegen tools never
had. A compiler names the exact symbol, file and line that broke, deterministically and for free,
where a browser console is noisy, late, and rarely names the cause.

Scope here is the invocation and its raw output (T019). Diagnostic-ID parsing and the
environment-vs-code-defect classification arrive with T044/T045.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Final

BUILD_TIMEOUT_SECONDS: Final[int] = 600
TEST_TIMEOUT_SECONDS: Final[int] = 900


class Classification(str, Enum):
    """Why a verification run ended. Drives whether a repair attempt may be spent."""

    PASS = "pass"
    CODE_DEFECT = "code_defect"
    ENVIRONMENT_FAILURE = "environment_failure"


@dataclass(frozen=True)
class CommandOutput:
    """One `dotnet` invocation's raw result."""

    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def combined(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()


@dataclass(frozen=True)
class VerificationResult:
    """The outcome of verifying a change, with the raw output that justifies it."""

    classification: Classification
    build: CommandOutput | None = None
    test: CommandOutput | None = None
    detail: str = ""
    diagnostics: tuple[object, ...] = field(default=())

    @property
    def passed(self) -> bool:
        return self.classification is Classification.PASS

    @property
    def repairable(self) -> bool:
        """Only a code defect may consume a repair attempt (FR-022)."""
        return self.classification is Classification.CODE_DEFECT

    def outputs(self) -> tuple[CommandOutput, ...]:
        return tuple(o for o in (self.build, self.test) if o is not None)


class ToolchainMissingError(RuntimeError):
    """`dotnet` is not on PATH. An environment failure, never a code defect."""


def _dotnet_executable() -> str:
    exe = shutil.which("dotnet")
    if exe is None:
        raise ToolchainMissingError("`dotnet` not found on PATH - install the .NET SDK")
    return exe


def run_command(args: tuple[str, ...], cwd: Path, timeout: int) -> CommandOutput:
    """Run one `dotnet` subcommand, never raising on a non-zero exit."""
    command = (_dotnet_executable(), *args)
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandOutput(
            command=command,
            exit_code=-1,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            timed_out=True,
        )
    except OSError as exc:
        return CommandOutput(command=command, exit_code=-1, stdout="", stderr=str(exc))

    return CommandOutput(
        command=command,
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def build(project: Path, *, timeout: int = BUILD_TIMEOUT_SECONDS) -> CommandOutput:
    return run_command(("build", "--nologo"), cwd=project, timeout=timeout)


def test(project: Path, *, filter_expression: str | None = None, timeout: int = TEST_TIMEOUT_SECONDS) -> CommandOutput:
    args: list[str] = ["test", "--nologo"]
    if filter_expression:
        args.extend(["--filter", filter_expression])
    return run_command(tuple(args), cwd=project, timeout=timeout)


def verify(
    project: Path,
    *,
    filter_expression: str | None = None,
    run_tests: bool = True,
) -> VerificationResult:
    """Build, then test if the build succeeded. Classification is provisional until T046-T047.

    Until the diagnostic parser lands, any failure is reported as a code defect *except* a
    missing toolchain or a timeout, which are unambiguously environmental. Erring toward
    code_defect here is deliberate: it keeps the retry budget honest rather than letting a real
    defect masquerade as an environment problem and skip the ceiling.
    """
    try:
        build_output = build(project)
    except ToolchainMissingError as exc:
        return VerificationResult(
            classification=Classification.ENVIRONMENT_FAILURE,
            detail=str(exc),
        )

    if build_output.timed_out:
        return VerificationResult(
            classification=Classification.ENVIRONMENT_FAILURE,
            build=build_output,
            detail="build timed out",
        )
    if not build_output.ok:
        return VerificationResult(
            classification=Classification.CODE_DEFECT,
            build=build_output,
            detail="build failed",
        )

    if not run_tests:
        return VerificationResult(classification=Classification.PASS, build=build_output)

    test_output = test(project, filter_expression=filter_expression)
    if test_output.timed_out:
        return VerificationResult(
            classification=Classification.ENVIRONMENT_FAILURE,
            build=build_output,
            test=test_output,
            detail="test run timed out",
        )
    if not test_output.ok:
        return VerificationResult(
            classification=Classification.CODE_DEFECT,
            build=build_output,
            test=test_output,
            detail="tests failed",
        )

    return VerificationResult(
        classification=Classification.PASS,
        build=build_output,
        test=test_output,
    )
