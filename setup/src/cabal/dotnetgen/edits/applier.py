# -*- coding: utf-8 -*-
"""Apply EditOperations to disk, recording every outcome — including failures.

Failed application is a *measured* cost, not an invisible retry (FR-018): an edit that does not
land burns a full turn and produces nothing, which is the most expensive outcome in the system.
So every attempt is recorded with the relaxation level it needed.

Scope here is the `create-file` disposition (T018) — enough for the greenfield path. Symbol
anchoring and the fuzzy relaxation ladder for existing members arrive with T038/T042.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from cabal.dotnetgen.edits.model import EditOperation

RELAXATION_EXACT = 0


class ApplyOutcome(str, Enum):
    """How an edit landed. Both applied states count as first-attempt successes for SC-003."""

    APPLIED = "applied"
    APPLIED_AFTER_RELAXATION = "applied_after_relaxation"
    FAILED = "failed"


@dataclass(frozen=True)
class EditApplication:
    """The record of one attempt, successful or not."""

    operation: EditOperation
    outcome: ApplyOutcome
    relaxation_level: int = RELAXATION_EXACT
    failure_reason: str = ""

    @property
    def landed(self) -> bool:
        return self.outcome is not ApplyOutcome.FAILED


@dataclass(frozen=True)
class ApplyReport:
    """The aggregate of one write stage's edits. `success_rate` is what SC-003 measures."""

    applications: tuple[EditApplication, ...]

    @property
    def landed(self) -> tuple[EditApplication, ...]:
        return tuple(a for a in self.applications if a.landed)

    @property
    def failed(self) -> tuple[EditApplication, ...]:
        return tuple(a for a in self.applications if not a.landed)

    @property
    def success_rate(self) -> float:
        if not self.applications:
            return 1.0
        return len(self.landed) / len(self.applications)

    @property
    def all_landed(self) -> bool:
        return not self.failed


class UnsupportedDispositionError(NotImplementedError):
    """Raised for a disposition whose applier has not landed yet, naming the task that adds it."""


_PENDING_DISPOSITIONS = {
    "replace": "T038/T042",
    "insert-into-type": "T038/T042",
    "delete": "T038/T042",
}


def _resolve(project: Path, relative: str) -> Path:
    """Resolve an operation path inside the project, refusing escapes."""
    target = (project / relative).resolve()
    root = project.resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"edit target {relative!r} escapes the project root")
    return target


def apply_operation(project: Path, operation: EditOperation) -> EditApplication:
    """Apply one operation, returning a record rather than raising on a failed application."""
    if operation.disposition != "create-file":
        task = _PENDING_DISPOSITIONS.get(operation.disposition)
        if task is not None:
            raise UnsupportedDispositionError(
                f"disposition {operation.disposition!r} is applied by {task}"
            )
        raise UnsupportedDispositionError(f"unknown disposition {operation.disposition!r}")

    try:
        target = _resolve(project, operation.file)
    except ValueError as exc:
        return EditApplication(operation, ApplyOutcome.FAILED, failure_reason=str(exc))

    if target.exists():
        return EditApplication(
            operation,
            ApplyOutcome.FAILED,
            failure_reason=f"{operation.file} already exists; create-file will not overwrite",
        )

    if operation.content is None:
        return EditApplication(
            operation, ApplyOutcome.FAILED, failure_reason="create-file requires content"
        )

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Written as bytes with explicit newlines: the platform default would rewrite line
        # endings and make every generated file look modified.
        target.write_bytes(operation.content.encode("utf-8"))
    except OSError as exc:
        return EditApplication(operation, ApplyOutcome.FAILED, failure_reason=str(exc))

    return EditApplication(operation, ApplyOutcome.APPLIED, relaxation_level=RELAXATION_EXACT)


def apply_all(project: Path, operations: tuple[EditOperation, ...]) -> ApplyReport:
    """Apply every operation, continuing past failures so the report is complete."""
    return ApplyReport(tuple(apply_operation(project, op) for op in operations))
