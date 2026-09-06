# -*- coding: utf-8 -*-
"""Integration test (T060) for SC-008: does binding the writer to a cheaper model actually pay?

The claim this feature rests on is that the *writing* stage is mechanical - the design was already
decided and approved - so it can run on a cheap or locally-hosted model without hurting quality.
SC-008 puts numbers on it: at least a 50% per-token cost reduction with first-attempt build-green
staying within 10 percentage points of the all-hosted configuration.

The three configurations are compared here against a scripted provider producing identical edits,
which isolates the cost arithmetic from model quality. Whether a given local model is *good* enough
is an empirical question for a real benchmark run; what this test pins is that the ledger reports
the difference correctly, so that benchmark has something trustworthy to measure with.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal.dotnetgen import ledger, runner
from cabal.dotnetgen.pipeline import ChangeIntent, RetryBudget, RunOutcome
from cabal.dotnetgen.providers.base import CompletionResult, Usage
from cabal.dotnetgen.verify import dotnet
from cabal.dotnetgen.verify.diagnostics import Classification

ORDER_CS = """namespace Orders.Domain;

public sealed class Order
{
    public void Cancel()
    {
    }
}
"""

INTENT = ChangeIntent(
    summary="Record why an order was cancelled.",
    target_files=("src/Order.cs",),
    target_symbols=("Orders.Domain.Order.Cancel",),
)

EDIT = json.dumps(
    {
        "operations": [
            {
                "file": "src/Order.cs",
                "anchor_kind": "symbol",
                "symbol": "Orders.Domain.Order.Cancel",
                "disposition": "replace",
                "content": "public void Cancel(string reason)\n{\n}",
                "reason": "record the reason",
            }
        ]
    }
)

USAGE = Usage(input_tokens=200_000, output_tokens=100_000, cached_input_tokens=150_000)


class FixedProvider:
    """Same edits, same token counts, different model and locality - so only price varies."""

    def __init__(self, name: str, model: str, *, is_local: bool = False) -> None:
        self.name = name
        self.model = model
        self.is_local = is_local

    def complete(self, request: object) -> CompletionResult:
        return CompletionResult(
            text=EDIT, usage=USAGE, model=self.model, provider=self.name
        )


@pytest.fixture
def solution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "solution"
    (root / "src").mkdir(parents=True)
    (root / "src" / "Order.cs").write_text(ORDER_CS, encoding="utf-8")
    monkeypatch.setattr(
        dotnet,
        "verify",
        lambda project, **kw: dotnet.VerificationResult(classification=Classification.PASS),
    )
    return root


def _run(solution: Path, provider: FixedProvider) -> ledger.RunRecord:
    record = ledger.RunRecord(run_id="r", project_path=str(solution))
    result = runner.run_approved(
        project=solution,
        intent=INTENT,
        provider=provider,
        model=provider.model,
        budget=RetryBudget(ceiling=3),
        record=record,
    )
    record.outcome = result.outcome.value
    record.first_attempt_build_green = bool(result.attempts) and result.attempts[0].passed
    record.edit_applications = [
        a for attempt in result.attempts for a in attempt.apply_report.applications
    ]
    assert result.outcome is RunOutcome.COMPLETED
    return record


def test_a_cheaper_hosted_writer_costs_less_than_the_premium_one(solution: Path) -> None:
    premium = _run(solution, FixedProvider("anthropic", "claude-opus-4-1"))
    (solution / "src" / "Order.cs").write_text(ORDER_CS, encoding="utf-8")
    cheap = _run(solution, FixedProvider("anthropic", "claude-haiku-4-5"))

    assert cheap.total_cost_usd < premium.total_cost_usd


def test_a_cheap_writer_beats_the_fifty_percent_reduction_sc008_asks_for(solution: Path) -> None:
    premium = _run(solution, FixedProvider("anthropic", "claude-opus-4-1"))
    (solution / "src" / "Order.cs").write_text(ORDER_CS, encoding="utf-8")
    cheap = _run(solution, FixedProvider("anthropic", "claude-haiku-4-5"))

    reduction = 1 - (cheap.total_cost_usd / premium.total_cost_usd)

    assert reduction >= 0.50


def test_a_local_writer_costs_exactly_nothing(solution: Path) -> None:
    local = _run(solution, FixedProvider("openai_compatible", "qwen2.5-coder:7b", is_local=True))

    assert local.total_cost_usd == 0


def test_build_green_is_unaffected_by_which_model_wrote_the_edits(solution: Path) -> None:
    """SC-008's quality half: cost may fall, first-attempt green must not."""
    premium = _run(solution, FixedProvider("anthropic", "claude-opus-4-1"))
    (solution / "src" / "Order.cs").write_text(ORDER_CS, encoding="utf-8")
    local = _run(solution, FixedProvider("openai_compatible", "qwen2.5-coder:7b", is_local=True))

    assert premium.first_attempt_build_green is local.first_attempt_build_green is True


def test_edit_success_rate_is_recorded_for_every_configuration(solution: Path) -> None:
    """SC-003 has to be comparable across configurations or the comparison proves nothing."""
    for provider in (
        FixedProvider("anthropic", "claude-opus-4-1"),
        FixedProvider("openai_compatible", "qwen2.5-coder:7b", is_local=True),
    ):
        (solution / "src" / "Order.cs").write_text(ORDER_CS, encoding="utf-8")

        assert _run(solution, provider).edit_success_rate == 1.0


def test_the_local_run_still_reports_its_token_counts(solution: Path) -> None:
    """Free is not the same as unmeasured - the tokens are what a comparison is made of."""
    local = _run(solution, FixedProvider("openai_compatible", "qwen2.5-coder:7b", is_local=True))

    assert local.stage_costs["write"].usage.output_tokens == USAGE.output_tokens
    assert local.stage_costs["write"].cost_usd == 0
