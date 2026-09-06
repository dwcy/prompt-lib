# -*- coding: utf-8 -*-
"""Unit tests for the approval gate, the retry budget, and the bounded repair loop."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from cabal.dotnetgen import pipeline
from cabal.dotnetgen.edits.applier import ApplyReport
from cabal.dotnetgen.edits.model import EditOperation
from cabal.dotnetgen.verify.dotnet import Classification, VerificationResult

INTENT = pipeline.ChangeIntent(
    summary="Add a cancel endpoint that refuses already-shipped orders.",
    target_files=("src/Orders.Api/Features/Cancel/CancelOrder.cs",),
    target_symbols=("Orders.Api.Features.Cancel.CancelOrderHandler.Handle",),
    rationale="Cancellation is a state transition on the order aggregate.",
)

OPERATION = EditOperation(
    file="src/Orders.Domain/Order.cs",
    anchor_kind="symbol",
    disposition="create-file",
    symbol="Orders.Domain.Order",
    content="namespace Orders.Domain;\n",
)

PASS = VerificationResult(classification=Classification.PASS)
DEFECT = VerificationResult(classification=Classification.CODE_DEFECT, detail="build failed")
ENVIRONMENT = VerificationResult(
    classification=Classification.ENVIRONMENT_FAILURE, detail="NU1101 package not found"
)


def _pipeline(results: Sequence[VerificationResult], ceiling: int = 3) -> pipeline.Pipeline:
    """A pipeline whose verifier yields the given outcomes in order."""
    remaining = list(results)
    writes: list[VerificationResult | None] = []

    def writer(intent, last_failure):
        writes.append(last_failure)
        return (OPERATION,)

    def applier(operations):
        return ApplyReport(())

    def verifier():
        return remaining.pop(0)

    built = pipeline.Pipeline(
        writer=writer, applier=applier, verifier=verifier, budget=pipeline.RetryBudget(ceiling)
    )
    built.writes = writes  # type: ignore[attr-defined]
    return built


# --- the gate ------------------------------------------------------------------------------


def test_rejected_intent_writes_nothing() -> None:
    def exploding_writer(intent, last_failure):
        raise AssertionError("the writer must not run on a rejected intent")

    built = pipeline.Pipeline(
        writer=exploding_writer, applier=lambda ops: ApplyReport(()), verifier=lambda: PASS
    )

    result = built.run(INTENT, pipeline.GateDecision.REJECTED)

    assert result.outcome is pipeline.RunOutcome.REJECTED_AT_GATE


def test_amended_intent_writes_nothing() -> None:
    built = _pipeline([PASS])

    result = built.run(INTENT, pipeline.GateDecision.AMENDED)

    assert result.outcome is pipeline.RunOutcome.REJECTED_AT_GATE


def test_approved_intent_runs_to_completion() -> None:
    built = _pipeline([PASS])

    result = built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert result.outcome is pipeline.RunOutcome.COMPLETED


def test_intent_containing_a_code_fence_is_refused() -> None:
    with pytest.raises(pipeline.IntentContainsCodeError):
        pipeline.ChangeIntent(summary="Do this:\n```csharp\nvar x = 1;\n```")


def test_intent_declaring_a_type_is_refused() -> None:
    with pytest.raises(pipeline.IntentContainsCodeError):
        pipeline.ChangeIntent(summary="Add public sealed class OrderCanceller to the domain.")


def test_prose_intent_naming_types_in_words_is_allowed() -> None:
    intent = pipeline.ChangeIntent(summary="Add a canceller to the Order aggregate in the domain.")

    assert intent.summary.startswith("Add a canceller")


# --- the budget ----------------------------------------------------------------------------


def test_fresh_budget_is_not_exhausted() -> None:
    assert pipeline.RetryBudget(3).exhausted is False


def test_zero_ceiling_is_exhausted_immediately() -> None:
    assert pipeline.RetryBudget(0).exhausted is True


def test_consuming_reduces_the_remaining_attempts() -> None:
    assert pipeline.RetryBudget(3).consume().remaining == 2


def test_consuming_past_the_ceiling_is_refused() -> None:
    spent = pipeline.RetryBudget(1).consume()

    with pytest.raises(pipeline.BudgetExhaustedError):
        spent.consume()


def test_a_budget_over_its_ceiling_cannot_be_constructed() -> None:
    """The invariant is absolute, so it is enforced at construction as well as at spend."""
    with pytest.raises(pipeline.BudgetExhaustedError):
        pipeline.RetryBudget(ceiling=2, consumed=3)


def test_negative_ceiling_is_refused() -> None:
    with pytest.raises(ValueError):
        pipeline.RetryBudget(ceiling=-1)


def test_environment_abort_does_not_consume_an_attempt() -> None:
    aborted = pipeline.RetryBudget(3).abort_environment()

    assert aborted.consumed == 0


# --- the repair loop -----------------------------------------------------------------------


def test_a_defect_then_a_pass_completes() -> None:
    built = _pipeline([DEFECT, PASS])

    result = built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert result.outcome is pipeline.RunOutcome.COMPLETED


def test_one_repair_costs_one_attempt() -> None:
    built = _pipeline([DEFECT, PASS])

    result = built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert result.budget.consumed == 1


def test_persistent_defects_halt_at_the_ceiling() -> None:
    built = _pipeline([DEFECT] * 10, ceiling=3)

    result = built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert result.outcome is pipeline.RunOutcome.HALTED_AT_CEILING


def test_halting_spends_exactly_the_ceiling() -> None:
    built = _pipeline([DEFECT] * 10, ceiling=3)

    result = built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert result.budget.consumed == result.budget.ceiling


def test_ceiling_of_three_makes_four_attempts() -> None:
    """One initial attempt plus three repairs - the ceiling counts repairs, not total tries."""
    built = _pipeline([DEFECT] * 10, ceiling=3)

    result = built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert len(result.attempts) == 4


def test_zero_ceiling_allows_no_repair() -> None:
    built = _pipeline([DEFECT] * 5, ceiling=0)

    result = built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert len(result.attempts) == 1


def test_environment_failure_aborts_the_run() -> None:
    built = _pipeline([ENVIRONMENT])

    result = built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert result.outcome is pipeline.RunOutcome.ABORTED_ENVIRONMENT


def test_environment_failure_leaves_the_budget_untouched() -> None:
    """Regenerating C# will never install a missing SDK, so spending on it is pure waste."""
    built = _pipeline([ENVIRONMENT], ceiling=3)

    result = built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert result.budget.consumed == 0


def test_environment_failure_after_a_repair_keeps_the_earlier_spend() -> None:
    built = _pipeline([DEFECT, ENVIRONMENT], ceiling=3)

    result = built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert (result.budget.consumed, result.budget.environment_aborts) == (1, 1)


def test_diagnostics_are_fed_back_to_the_writer() -> None:
    """The failure must reach the writing stage; routing it to the architect would re-decide design."""
    built = _pipeline([DEFECT, PASS])

    built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert built.writes == [None, DEFECT]  # type: ignore[attr-defined]


def test_every_attempt_is_recorded_on_a_halted_run() -> None:
    built = _pipeline([DEFECT] * 10, ceiling=2)

    result = built.run(INTENT, pipeline.GateDecision.APPROVED)

    assert [a.number for a in result.attempts] == [1, 2, 3]
