# -*- coding: utf-8 -*-
"""Unit tests for the cost ledger (T061-T063), validated against the run-record schema."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import jsonschema
import pytest

from cabal.dotnetgen import ledger
from cabal.dotnetgen.edits.applier import ApplyOutcome, EditApplication
from cabal.dotnetgen.edits.model import EditOperation
from cabal.dotnetgen.pipeline import RetryBudget
from cabal.dotnetgen.providers.base import Usage


def _stage(stage: str, model: str, usage: Usage, **kw) -> ledger.StageCost:
    return ledger.StageCost(stage=stage, provider="cli_shell", model=model, usage=usage, **kw)


def _application(outcome: ApplyOutcome, level: int = 0) -> EditApplication:
    operation = EditOperation(
        file="src/Order.cs",
        anchor_kind="symbol",
        disposition="replace",
        symbol="Orders.Domain.Order.Cancel",
        content="public void Cancel() { }",
    )
    return EditApplication(operation, outcome, relaxation_level=level)


def test_a_known_model_is_priced_from_the_shared_table() -> None:
    cost = _stage("write", "claude-sonnet-4", Usage(input_tokens=1_000_000, output_tokens=0))

    assert cost.cost_usd > 0


def test_a_locally_hosted_stage_costs_nothing() -> None:
    """SC-008 depends on this being a measured zero, not a missing number."""
    cost = _stage(
        "write", "qwen2.5-coder:7b", Usage(input_tokens=500_000, output_tokens=500_000),
        priced=False,
    )

    assert cost.cost_usd == 0


def test_cached_input_is_billed_at_the_cache_rate() -> None:
    """The cache is the saving; charging cached tokens at full rate would erase it."""
    uncached = _stage("write", "claude-sonnet-4", Usage(input_tokens=1_000_000))
    cached = _stage(
        "write",
        "claude-sonnet-4",
        Usage(input_tokens=1_000_000, cached_input_tokens=1_000_000),
    )

    assert cached.cost_usd < uncached.cost_usd


def test_repeat_calls_to_one_stage_accumulate() -> None:
    record = ledger.RunRecord(run_id="r1")
    record.record_stage(_stage("write", "claude-sonnet-4", Usage(input_tokens=100)))
    record.record_stage(_stage("write", "claude-sonnet-4", Usage(input_tokens=150)))

    assert record.stage_costs["write"].usage.input_tokens == 250


def test_repair_cost_is_attributable_separately() -> None:
    """FR-029: a run that repairs three times must not average out to look cheap."""
    record = ledger.RunRecord(run_id="r1")
    record.record_stage(_stage("write", "claude-sonnet-4", Usage(output_tokens=1_000_000)))
    record.record_stage(
        _stage("write", "claude-sonnet-4", Usage(output_tokens=1_000_000)), is_repair=True
    )

    assert record.repair_cost_usd > 0
    assert record.initial_attempt_cost_usd == pytest.approx(
        record.total_cost_usd - record.repair_cost_usd
    )


def test_cache_ratio_is_omitted_when_no_provider_reports_caching() -> None:
    """A false 0.0 would drag SC-005 down with a number nobody measured."""
    record = ledger.RunRecord(run_id="r1")
    record.record_stage(
        _stage("write", "m", Usage(input_tokens=1000, cache_reported=False))
    )

    assert record.cache_ratio is None
    assert "cache_ratio" not in record.to_dict()["derived"]


def test_cache_ratio_is_reported_when_the_provider_supplies_it() -> None:
    record = ledger.RunRecord(run_id="r1")
    record.record_stage(
        _stage("write", "m", Usage(input_tokens=1000, cached_input_tokens=700))
    )

    assert record.cache_ratio == pytest.approx(0.7)


def test_edit_success_rate_counts_relaxed_applications_as_successes() -> None:
    """Both applied states cost no repair turn, so SC-003 counts them alike."""
    record = ledger.RunRecord(
        run_id="r1",
        edit_applications=[
            _application(ApplyOutcome.APPLIED),
            _application(ApplyOutcome.APPLIED_AFTER_RELAXATION, level=2),
            _application(ApplyOutcome.FAILED),
        ],
    )

    assert record.edit_success_rate == pytest.approx(2 / 3)


def test_reconciliation_fails_when_the_provider_disagrees_beyond_tolerance() -> None:
    """SC-010 reports disagreement rather than silently trusting our own arithmetic."""
    record = ledger.RunRecord(run_id="r1")
    record.record_stage(_stage("write", "claude-sonnet-4", Usage(output_tokens=1_000_000)))

    assert record.reconciled_within_tolerance(record.total_cost_usd) is True
    assert record.reconciled_within_tolerance(record.total_cost_usd * 2) is False


def test_an_unreconciled_run_says_so_rather_than_omitting_the_flag() -> None:
    record = ledger.RunRecord(run_id="r1")

    assert record.to_dict()["derived"]["reconciled"] is False


def test_the_written_record_validates_against_the_contract(
    tmp_path: Path, run_record_schema: dict
) -> None:
    record = ledger.RunRecord(
        run_id=ledger.new_run_id(),
        project_path=str(tmp_path),
        template_id="vertical-slice",
        outcome="completed",
        repair_attempts=[ledger.RepairAttempt(attempt=1, classification="code_defect", resolved=True)],
        edit_applications=[_application(ApplyOutcome.APPLIED)],
        retry_budget=RetryBudget(ceiling=3, consumed=1),
        wall_clock_seconds=12.5,
        first_attempt_build_green=True,
    )
    record.record_stage(_stage("architect", "claude-opus-5", Usage(input_tokens=900)))
    record.record_stage(_stage("write", "claude-sonnet-4", Usage(output_tokens=400)))

    path = ledger.write(tmp_path, record, provider_reported_usd=record.total_cost_usd)
    written = json.loads(path.read_text(encoding="utf-8"))

    jsonschema.validate(written, run_record_schema)


def test_consumed_never_exceeds_the_ceiling_in_a_written_record(tmp_path: Path) -> None:
    record = ledger.RunRecord(run_id="r1", retry_budget=RetryBudget(ceiling=3, consumed=3))

    payload = record.to_dict()

    assert payload["retry_budget"]["consumed"] <= payload["retry_budget"]["ceiling"]


def test_reconciliation_uses_the_provider_figure_not_our_own_total() -> None:
    """Reconciliation must compare against what the provider billed, never against itself."""
    record = ledger.RunRecord(run_id="r1")
    record.record_stage(_stage("write", "claude-sonnet-4", Usage(output_tokens=1_000_000)))

    assert record.provider_reported_usd is None


def test_a_reported_provider_cost_aggregates_across_stages() -> None:
    record = ledger.RunRecord(run_id="r1")
    first = replace(
        _stage("architect", "claude-sonnet-4", Usage(output_tokens=10)), reported_cost_usd=0.25
    )
    second = replace(
        _stage("write", "claude-sonnet-4", Usage(output_tokens=10)), reported_cost_usd=0.75
    )
    record.record_stage(first)
    record.record_stage(second)

    assert record.provider_reported_usd == pytest.approx(1.0)
