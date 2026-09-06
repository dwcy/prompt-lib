# -*- coding: utf-8 -*-
"""Stage orchestration, the approval gate, and the bounded repair loop.

The one cycle in this design is write -> apply -> verify -> write, and it is bounded. That is the
structural answer to the documented failure mode of the frontend codegen tools, where users pay
full price for the tool to fix its own breakage. Two rules keep it honest:

* only a **code defect** may consume a repair attempt; an environment failure aborts at zero
  consumed, because regenerating C# will never install a missing SDK (FR-022)
* diagnostics route back to the **writing** stage, never the architect stage — re-deciding the
  design would also invalidate cache bands 1-3 (FR-020, research R5)

Stages arrive as injected callables so the loop, the gate and the budget are testable now and the
concrete architect/write stages plug in with their own tasks.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Final

from cabal.dotnetgen.edits.applier import ApplyReport
from cabal.dotnetgen.edits.model import EditOperation
from cabal.dotnetgen.verify.dotnet import Classification, VerificationResult

DEFAULT_RETRY_CEILING: Final[int] = 3

# A prose intent must not smuggle code past the gate; the developer is approving a description.
_CODE_MARKERS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"```"),
    re.compile(r"\bnamespace\s+[\w.]+\s*[;{]"),
    re.compile(r"\b(?:public|private|internal|protected)\s+(?:sealed\s+|static\s+|partial\s+)*"
               r"(?:class|record|struct|interface|enum)\b"),
    re.compile(r"=>\s*\w+\("),
)


class RunOutcome(str, Enum):
    """How a run ended. Mirrors the `outcome` enum in the run-record contract."""

    COMPLETED = "completed"
    HALTED_AT_CEILING = "halted_at_ceiling"
    ABORTED_ENVIRONMENT = "aborted_environment"
    REJECTED_AT_GATE = "rejected_at_gate"


class GateDecision(str, Enum):
    """What the developer did at the approval gate."""

    APPROVED = "approved"
    REJECTED = "rejected"
    AMENDED = "amended"


class BudgetExhaustedError(RuntimeError):
    """Raised when a repair attempt is requested beyond the ceiling."""


class IntentContainsCodeError(ValueError):
    """Raised when the architect stage emits code instead of prose."""


@dataclass(frozen=True)
class RetryBudget:
    """The hard ceiling on repair attempts, and what has been spent against it."""

    ceiling: int = DEFAULT_RETRY_CEILING
    consumed: int = 0
    environment_aborts: int = 0

    def __post_init__(self) -> None:
        if self.ceiling < 0:
            raise ValueError(f"ceiling must be non-negative, got {self.ceiling}")
        if self.consumed > self.ceiling:
            raise BudgetExhaustedError(
                f"consumed {self.consumed} exceeds ceiling {self.ceiling}; the invariant is absolute"
            )

    @property
    def exhausted(self) -> bool:
        return self.consumed >= self.ceiling

    @property
    def remaining(self) -> int:
        return self.ceiling - self.consumed

    def consume(self) -> "RetryBudget":
        """Spend one attempt on a code defect."""
        if self.exhausted:
            raise BudgetExhaustedError(f"retry ceiling {self.ceiling} already reached")
        return replace(self, consumed=self.consumed + 1)

    def abort_environment(self) -> "RetryBudget":
        """Record an environment failure. Deliberately does not touch `consumed`."""
        return replace(self, environment_aborts=self.environment_aborts + 1)


@dataclass(frozen=True)
class ChangeIntent:
    """The architect stage's output: prose the developer approves, containing no code."""

    summary: str
    target_files: tuple[str, ...] = ()
    target_symbols: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        for text in (self.summary, self.rationale):
            for pattern in _CODE_MARKERS:
                match = pattern.search(text)
                if match is not None:
                    raise IntentContainsCodeError(
                        f"intent contains code ({match.group(0)!r}); the gate approves prose, "
                        "and writing code before approval would spend the tokens the gate exists "
                        "to save"
                    )


@dataclass(frozen=True)
class Attempt:
    """One pass through write -> apply -> verify, recorded whether or not it succeeded."""

    number: int
    apply_report: ApplyReport
    verification: VerificationResult

    @property
    def passed(self) -> bool:
        return self.verification.passed


@dataclass(frozen=True)
class RunResult:
    """The outcome of one pipeline run, with every attempt it made."""

    outcome: RunOutcome
    budget: RetryBudget
    intent: ChangeIntent | None = None
    attempts: tuple[Attempt, ...] = field(default=())
    detail: str = ""

    @property
    def succeeded(self) -> bool:
        return self.outcome is RunOutcome.COMPLETED

    def history(self) -> tuple[str, ...]:
        """One line per attempt, so a halted run explains itself without the raw logs (FR-023)."""
        lines: list[str] = []
        for attempt in self.attempts:
            landed = len(attempt.apply_report.landed)
            total = len(attempt.apply_report.applications)
            verdict = attempt.verification.classification.value
            detail = attempt.verification.detail or verdict
            lines.append(f"attempt {attempt.number}: {landed}/{total} edits applied - {detail}")
        return tuple(lines)

    def report(self) -> str:
        """The halt report: what was tried, what remains wrong, and where to look."""
        lines = [f"outcome: {self.outcome.value}", *self.history()]
        if self.detail:
            lines.append(self.detail)
        lines.append(
            f"repair attempts consumed: {self.budget.consumed}/{self.budget.ceiling}"
        )
        return "\n".join(lines)


Writer = Callable[[ChangeIntent, VerificationResult | None], Sequence[EditOperation]]
Applier = Callable[[Sequence[EditOperation]], ApplyReport]
Verifier = Callable[[], VerificationResult]


@dataclass
class Pipeline:
    """Sequences the stages, holds the gate, and enforces the ceiling.

    Note what this class does *not* hold: an architect. Repair routing (FR-020) is enforced
    structurally rather than by discipline - a diagnostic can only reach `writer`, because the
    loop has no reference to any stage that could re-decide the design. That also protects the
    cache: re-running the architect would rewrite bands 1-3 and discard the whole cached prefix
    on every repair (research R5).
    """

    writer: Writer
    applier: Applier
    verifier: Verifier
    budget: RetryBudget = field(default_factory=RetryBudget)

    def run(self, intent: ChangeIntent, decision: GateDecision) -> RunResult:
        """Execute an intent that has passed the gate, repairing up to the ceiling."""
        if decision is not GateDecision.APPROVED:
            return RunResult(
                outcome=RunOutcome.REJECTED_AT_GATE,
                budget=self.budget,
                intent=intent,
                detail=f"gate decision was {decision.value}; no code was written",
            )

        attempts: list[Attempt] = []
        budget = self.budget
        last_failure: VerificationResult | None = None

        while True:
            number = len(attempts) + 1
            operations = tuple(self.writer(intent, last_failure))
            report = self.applier(operations)
            verification = self.verifier()
            attempts.append(Attempt(number, report, verification))

            if verification.passed:
                return RunResult(RunOutcome.COMPLETED, budget, intent, tuple(attempts))

            if verification.classification is Classification.ENVIRONMENT_FAILURE:
                return RunResult(
                    outcome=RunOutcome.ABORTED_ENVIRONMENT,
                    budget=budget.abort_environment(),
                    intent=intent,
                    attempts=tuple(attempts),
                    detail=(
                        f"{verification.detail}; environment failures never consume the repair "
                        "budget"
                    ),
                )

            if budget.exhausted:
                return RunResult(
                    outcome=RunOutcome.HALTED_AT_CEILING,
                    budget=budget,
                    intent=intent,
                    attempts=tuple(attempts),
                    detail=(
                        f"retry ceiling {budget.ceiling} reached after {len(attempts)} attempts; "
                        f"last failure: {verification.detail or verification.classification.value}. "
                        "The working tree is left exactly as the final attempt produced it, so the "
                        "partial work can be inspected or salvaged rather than discarded"
                    ),
                )

            budget = budget.consume()
            last_failure = verification
