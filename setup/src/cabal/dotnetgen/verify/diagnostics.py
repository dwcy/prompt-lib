# -*- coding: utf-8 -*-
"""Parse .NET diagnostics and decide whether a failure may consume a repair attempt.

This is the module that makes unattended running safe. The .NET toolchain emits structured,
prefixed diagnostic IDs, which is the deterministic signal the frontend codegen tools never had -
a browser console is noisy, late, and rarely names the cause, whereas `CS1002` names the file,
the line and the mistake for free.

The classification rule is research R4, and its one non-obvious refinement is here: an `MSB####`
raised against a file *this run just wrote* is a code defect, not an environment failure. The tool
broke the `.csproj`; that is repairable and should cost an attempt. An `MSB####` against anything
else is environmental and must not.

Why the asymmetry matters: repairing a missing SDK by regenerating C# is exactly the runaway loop
FR-021 exists to prevent. Environment failures therefore consume zero attempts and abort at once.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from cabal.dotnetgen.verify.dotnet import CommandOutput


class Classification(str, Enum):
    """Why a verification run ended. Drives whether a repair attempt may be spent.

    Defined here rather than in `dotnet.py` because classification is this module's subject and
    `dotnet.py` depends on it - the dependency has to run one way.
    """

    PASS = "pass"
    CODE_DEFECT = "code_defect"
    ENVIRONMENT_FAILURE = "environment_failure"


_DIAGNOSTIC = re.compile(
    r"(?P<file>[^\s(][^(]*)?\(?\d*,?\d*\)?\s*:?\s*"
    r"(?:error|warning)\s+"
    r"(?P<id>(?P<prefix>CS|NU|MSB|NETSDK|IDE|CA|SA)(?P<number>\d+))\s*:\s*"
    r"(?P<message>.*)",
    re.IGNORECASE,
)

_XUNIT_FAILURE = re.compile(r"^\s*(?:\[xUnit.*\]\s*)?(?:Failed|Assert\.\w+\(\) Failure)", re.M)
_TEST_FAILED_COUNT = re.compile(r"Failed:\s*(\d+)", re.IGNORECASE)

CODE_DEFECT_PREFIXES: Final[frozenset[str]] = frozenset({"CS", "IDE", "CA", "SA"})
"""Compiler and analyzer diagnostics. The code, or the repo's own rules, are being violated."""

ENVIRONMENT_PREFIXES: Final[frozenset[str]] = frozenset({"NU", "NETSDK"})
"""Restore, feed, auth, offline, SDK targeting. Regenerating C# will never fix these."""


@dataclass(frozen=True)
class Diagnostic:
    """One parsed toolchain diagnostic."""

    id: str
    prefix: str
    message: str
    file: str | None = None

    @property
    def is_code_defect(self) -> bool:
        return self.prefix in CODE_DEFECT_PREFIXES


def parse(text: str) -> tuple[Diagnostic, ...]:
    """Extract every diagnostic from build or test output, preserving order and duplicates."""
    found: list[Diagnostic] = []
    for match in _DIAGNOSTIC.finditer(text):
        raw_file = (match.group("file") or "").strip().rstrip(":").strip()
        found.append(
            Diagnostic(
                id=match.group("id").upper(),
                prefix=match.group("prefix").upper(),
                message=match.group("message").strip(),
                file=raw_file or None,
            )
        )
    return tuple(found)


def has_test_failures(output: "CommandOutput | None") -> bool:
    """True when `dotnet test` reported at least one failing test, not merely a non-zero exit."""
    if output is None:
        return False
    text = output.combined
    counted = _TEST_FAILED_COUNT.search(text)
    if counted is not None:
        return int(counted.group(1)) > 0
    return _XUNIT_FAILURE.search(text) is not None


def classify(
    diagnostics: tuple[Diagnostic, ...],
    *,
    written_files: frozenset[str] = frozenset(),
    test_failures: bool = False,
) -> Classification:
    """Apply research R4: diagnostic prefix first, then test failures, then absence of signal.

    `written_files` are solution-relative paths this run authored. They are what makes the
    `MSB####` refinement possible: the same diagnostic means different things depending on whether
    the tool wrote the file it fired against.
    """
    if test_failures:
        return Classification.CODE_DEFECT

    if any(d.is_code_defect for d in diagnostics):
        return Classification.CODE_DEFECT

    msbuild = [d for d in diagnostics if d.prefix == "MSB"]
    if msbuild and any(_names_written_file(d, written_files) for d in msbuild):
        return Classification.CODE_DEFECT

    if diagnostics:
        return Classification.ENVIRONMENT_FAILURE

    # Non-zero exit with nothing parsed: a crash, a missing tool, a permissions problem.
    # Never spend a repair attempt on a failure the toolchain could not even describe.
    return Classification.ENVIRONMENT_FAILURE


def _names_written_file(diagnostic: Diagnostic, written_files: frozenset[str]) -> bool:
    if diagnostic.file is None:
        return False
    normalised = diagnostic.file.replace("\\", "/").lower()
    return any(normalised.endswith(w.replace("\\", "/").lower()) for w in written_files)
