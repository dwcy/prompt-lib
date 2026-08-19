# -*- coding: utf-8 -*-
"""Apply EditOperations to disk, recording every outcome — including failures.

Failed application is a *measured* cost, not an invisible retry (FR-018): an edit that does not
land burns a full turn and produces nothing, which is the most expensive outcome in the system.
So every attempt is recorded with the relaxation level it needed.

Every disposition is applied here. Member-scoped edits resolve through `anchor_csharp`, which
re-reads the file and finds the symbol afresh, so `dotnet format` running between write and apply
cannot invalidate them. Non-member edits fall back to `relaxation`'s ladder and record which rung
they needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from cabal.dotnetgen.edits import anchor_csharp, relaxation
from cabal.dotnetgen.edits.model import EditOperation
from cabal.dotnetgen.edits.relaxation import RELAXATION_EXACT


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
    """Raised for a disposition this applier does not know how to perform."""


def _resolve(project: Path, relative: str) -> Path:
    """Resolve an operation path inside the project, refusing escapes."""
    target = (project / relative).resolve()
    root = project.resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"edit target {relative!r} escapes the project root")
    return target


def apply_operation(project: Path, operation: EditOperation) -> EditApplication:
    """Apply one operation, returning a record rather than raising on a failed application."""
    try:
        target = _resolve(project, operation.file)
    except ValueError as exc:
        return EditApplication(operation, ApplyOutcome.FAILED, failure_reason=str(exc))

    if operation.disposition != "create-file":
        return _apply_in_place(target, operation)

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


def _apply_in_place(target: Path, operation: EditOperation) -> EditApplication:
    """Edit a file that already exists: resolve the anchor against its current text, then write.

    The anchor is resolved here rather than at write time on purpose. Between the model proposing
    an edit and this function running, the file may have been reformatted or changed by an earlier
    operation in the same batch; re-resolving is what makes that harmless.
    """
    if not target.is_file():
        return EditApplication(
            operation,
            ApplyOutcome.FAILED,
            failure_reason=f"{operation.file} does not exist; use create-file to add it",
        )

    source = target.read_text(encoding="utf-8")
    try:
        updated, level = _rewrite(source, operation)
    except (anchor_csharp.AnchorError, LookupError) as exc:
        return EditApplication(operation, ApplyOutcome.FAILED, failure_reason=str(exc))
    except UnsupportedDispositionError as exc:
        return EditApplication(operation, ApplyOutcome.FAILED, failure_reason=str(exc))

    if updated == source:
        return EditApplication(
            operation,
            ApplyOutcome.FAILED,
            failure_reason="edit produced no change; a no-op costs a turn and gains nothing",
        )

    try:
        target.write_bytes(updated.encode("utf-8"))
    except OSError as exc:
        return EditApplication(operation, ApplyOutcome.FAILED, failure_reason=str(exc))

    outcome = ApplyOutcome.APPLIED if level == RELAXATION_EXACT else ApplyOutcome.APPLIED_AFTER_RELAXATION
    return EditApplication(operation, outcome, relaxation_level=level)


def _rewrite(source: str, operation: EditOperation) -> tuple[str, int]:
    """Produce the file's new text for one non-create disposition, and the rung it needed."""
    if operation.disposition == "insert-into-type":
        if operation.anchor_kind != "symbol":
            raise UnsupportedDispositionError("insert-into-type requires a symbol anchor")
        return anchor_csharp.insert_into_type(
            source, operation.anchor, operation.content or ""
        ), RELAXATION_EXACT

    if operation.anchor_kind == "symbol":
        span = anchor_csharp.resolve(source, operation.anchor)
        if operation.disposition == "delete":
            return _cut(source, span.start, span.end), RELAXATION_EXACT
        return span.replaced_with(source, operation.content or ""), RELAXATION_EXACT

    if operation.disposition == "delete":
        match = relaxation.find(source, operation.anchor)
        if match is None:
            raise relaxation.AnchorNotFoundError(
                f"anchor text not found at any relaxation level: {operation.anchor[:80]!r}"
            )
        return _cut(source, match.start, match.end), match.level

    updated, match = relaxation.replace(source, operation.anchor, operation.content or "")
    return updated, match.level


def _cut(source: str, start: int, end: int) -> str:
    """Remove a span, taking the rest of its line with it so no blank stub is left behind."""
    line_start = source.rfind("\n", 0, start) + 1
    if source[line_start:start].strip() == "":
        start = line_start
    line_end = source.find("\n", end)
    if line_end != -1 and source[end:line_end].strip() == "":
        end = line_end + 1
    return source[:start] + source[end:]


def apply_all(project: Path, operations: tuple[EditOperation, ...]) -> ApplyReport:
    """Apply every operation, continuing past failures so the report is complete."""
    return ApplyReport(tuple(apply_operation(project, op) for op in operations))
