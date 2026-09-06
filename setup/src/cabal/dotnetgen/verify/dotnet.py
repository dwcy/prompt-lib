# -*- coding: utf-8 -*-
"""Verification via the .NET toolchain: run `dotnet build`, then `dotnet test`, and capture the result.

This is the pipeline's feedback signal, and it is the component the frontend codegen tools never
had. A compiler names the exact symbol, file and line that broke, deterministically and for free,
where a browser console is noisy, late, and rarely names the cause.

Scope here is the invocation and the decision it produces. The parsing and classification rules
themselves live in `diagnostics.py`, which this module depends on.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from cabal.dotnetgen.verify import diagnostics
from cabal.dotnetgen.verify.diagnostics import Classification, Diagnostic

BUILD_TIMEOUT_SECONDS: Final[int] = 600
TEST_TIMEOUT_SECONDS: Final[int] = 900


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
    diagnostics: tuple[Diagnostic, ...] = field(default=())

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
    written_files: frozenset[str] = frozenset(),
) -> VerificationResult:
    """Build, then test if the build succeeded, and classify any failure per research R4.

    `written_files` are solution-relative paths this run authored. They exist for one rule: an
    MSB#### diagnostic fired against a file the tool itself just wrote is a code defect (the tool
    broke the .csproj, and that is repairable), while the same diagnostic anywhere else is an
    environment problem. Without that distinction the tool would either never repair its own
    project files, or would burn the whole retry budget on a broken SDK install.
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
        found = diagnostics.parse(build_output.combined)
        classification = diagnostics.classify(found, written_files=written_files)
        return VerificationResult(
            classification=classification,
            build=build_output,
            detail=_describe(found, "build failed"),
            diagnostics=found,
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
        found = diagnostics.parse(test_output.combined)
        classification = diagnostics.classify(
            found,
            written_files=written_files,
            test_failures=diagnostics.has_test_failures(test_output),
        )
        return VerificationResult(
            classification=classification,
            build=build_output,
            test=test_output,
            detail=_describe(found, "tests failed"),
            diagnostics=found,
        )

    return VerificationResult(
        classification=Classification.PASS,
        build=build_output,
        test=test_output,
    )


def _describe(found: tuple[Diagnostic, ...], fallback: str) -> str:
    """Name the diagnostics that drove the classification, so a halt report is actionable."""
    if not found:
        return f"{fallback}; no diagnostics parsed"
    ids = sorted({d.id for d in found})
    return f"{fallback}: {', '.join(ids[:6])}" + (" and others" if len(ids) > 6 else "")
