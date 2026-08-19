# -*- coding: utf-8 -*-
"""Per-run cost accounting: what each stage spent, and what that says about the design.

The whole feature rests on a claim - that routing, a cached prefix, symbol-anchored edits and a
bounded repair loop cost less than a naive loop. Without this module that claim is an opinion.
SC-002, SC-005, SC-008 and SC-010 are all measured from what is recorded here.

Three things it is careful about:

* **Repair cost is separated from initial cost** (FR-029). A pipeline that looks cheap per call
  but repairs three times is not cheap, and averaging the two together hides exactly that.
* **A local model costs zero, and that is a real number, not a missing one** (SC-008). An unknown
  model also prices at zero, so the two are distinguished by `priced`, never conflated.
* **Cache figures are only reported when the provider reports them.** `Usage.cache_reported` is
  false for providers that cannot say, and inventing a ratio there would corrupt SC-005.

Written to `.dotnetgen/runs/<run-id>.json` against `contracts/run-record.schema.json`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from cabal import session_pricing
from cabal.dotnetgen.edits.applier import ApplyOutcome, EditApplication
from cabal.dotnetgen.pipeline import RetryBudget, RunResult
from cabal.dotnetgen.providers.base import Usage

RUNS_RELDIR: Final[str] = ".dotnetgen/runs"
RECONCILE_TOLERANCE: Final[float] = 0.05
"""SC-010 allows 5% drift between our arithmetic and the provider's own reported usage."""

def prices_nothing(provider: object) -> bool:
    """True when the provider runs on this machine and therefore bills nothing (SC-008).

    Asked of the provider instance, never inferred from its name. `openai_compatible` serves both
    Ollama on localhost and hosted OpenAI; deciding by name would report a hosted run as free and
    quietly corrupt the one number SC-008 turns on.
    """
    return bool(getattr(provider, "is_local", False))


@dataclass(frozen=True)
class StageCost:
    """One stage's spend. `priced` distinguishes 'free' from 'we do not know the price'."""

    stage: str
    provider: str
    model: str
    usage: Usage = field(default_factory=Usage)
    wall_clock_seconds: float = 0.0
    priced: bool = True

    @property
    def cost_usd(self) -> float:
        if not self.priced:
            return 0.0
        entry = session_pricing.lookup(self.model, session_pricing.load_pricing())
        uncached = self.usage.uncached_input_tokens
        return (
            uncached * entry.input_usd_per_mtok
            + self.usage.cached_input_tokens * entry.cache_read_usd_per_mtok
            + self.usage.output_tokens * entry.output_usd_per_mtok
        ) / 1_000_000

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.usage.input_tokens,
            "cached_input_tokens": self.usage.cached_input_tokens,
            "output_tokens": self.usage.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "wall_clock_seconds": round(self.wall_clock_seconds, 3),
        }


@dataclass(frozen=True)
class RepairAttempt:
    """One repair turn, with what provoked it and what it cost.

    Per-attempt rather than a bare count so FR-029 can answer "what did the repairs cost?" and
    SC-007 can show that an environment failure consumed nothing.
    """

    attempt: int
    classification: str
    cost_usd: float = 0.0
    diagnostic_ids: tuple[str, ...] = field(default=())
    resolved: bool = False

    def to_dict(self) -> dict:
        payload: dict[str, object] = {
            "attempt": self.attempt,
            "classification": self.classification,
            "cost_usd": round(self.cost_usd, 6),
            "resolved": self.resolved,
        }
        if self.diagnostic_ids:
            payload["diagnostic_ids"] = list(self.diagnostic_ids)
        return payload


@dataclass
class RunRecord:
    """One pipeline run's ledger. Mutable while the run is in flight, then written once."""

    run_id: str
    project_path: str = ""
    template_id: str = ""
    outcome: str = "completed"
    stage_costs: dict[str, StageCost] = field(default_factory=dict)
    repair_attempts: list[RepairAttempt] = field(default_factory=list)
    edit_applications: list[EditApplication] = field(default_factory=list)
    retry_budget: RetryBudget = field(default_factory=RetryBudget)
    wall_clock_seconds: float = 0.0
    first_attempt_build_green: bool = False
    repair_stage_costs: list[StageCost] = field(default_factory=list)

    def record_stage(self, cost: StageCost, *, is_repair: bool = False) -> None:
        """Add one stage call. Repeat calls to a stage accumulate rather than overwrite."""
        existing = self.stage_costs.get(cost.stage)
        if existing is None:
            self.stage_costs[cost.stage] = cost
        else:
            self.stage_costs[cost.stage] = replace(
                existing,
                usage=existing.usage + cost.usage,
                wall_clock_seconds=existing.wall_clock_seconds + cost.wall_clock_seconds,
                priced=existing.priced and cost.priced,
            )
        if is_repair:
            self.repair_stage_costs.append(cost)

    @property
    def total_cost_usd(self) -> float:
        return sum(cost.cost_usd for cost in self.stage_costs.values())

    @property
    def repair_cost_usd(self) -> float:
        """What the repairs cost. Kept apart so a cheap-but-repetitive run cannot look cheap."""
        return sum(cost.cost_usd for cost in self.repair_stage_costs)

    @property
    def initial_attempt_cost_usd(self) -> float:
        return max(0.0, self.total_cost_usd - self.repair_cost_usd)

    @property
    def cache_ratio(self) -> float | None:
        """Cached share of input across every stage, or None when no provider reported caching."""
        reporting = [c.usage for c in self.stage_costs.values() if c.usage.cache_reported]
        total_input = sum(u.input_tokens for u in reporting)
        if not reporting or total_input <= 0:
            return None
        return sum(u.cached_input_tokens for u in reporting) / total_input

    @property
    def edit_success_rate(self) -> float:
        if not self.edit_applications:
            return 1.0
        landed = sum(1 for a in self.edit_applications if a.landed)
        return landed / len(self.edit_applications)

    def reconciled_within_tolerance(self, provider_reported_usd: float | None) -> bool:
        """SC-010: our arithmetic must agree with the provider, and disagreement is reported."""
        if provider_reported_usd is None:
            return False
        ours = self.total_cost_usd
        if provider_reported_usd == 0:
            return ours == 0
        return abs(ours - provider_reported_usd) / provider_reported_usd <= RECONCILE_TOLERANCE

    def to_dict(self, provider_reported_usd: float | None = None) -> dict:
        return {
            "run_id": self.run_id,
            "project_path": self.project_path,
            "template_id": self.template_id,
            "outcome": self.outcome,
            "stage_costs": {name: cost.to_dict() for name, cost in self.stage_costs.items()},
            "repair_attempts": [a.to_dict() for a in self.repair_attempts],
            "edit_applications": [_edit_to_dict(a) for a in self.edit_applications],
            "retry_budget": {
                "ceiling": self.retry_budget.ceiling,
                "consumed": self.retry_budget.consumed,
                "environment_aborts": self.retry_budget.environment_aborts,
            },
            "derived": _derived(self, provider_reported_usd),
            "wall_clock_seconds": round(self.wall_clock_seconds, 3),
        }


def _derived(record: RunRecord, provider_reported_usd: float | None) -> dict:
    derived: dict[str, object] = {
        "edit_success_rate": round(record.edit_success_rate, 4),
        "first_attempt_build_green": record.first_attempt_build_green,
        "initial_attempt_cost_usd": round(record.initial_attempt_cost_usd, 6),
        "repair_cost_usd": round(record.repair_cost_usd, 6),
        "reconciled": record.reconciled_within_tolerance(provider_reported_usd),
    }
    ratio = record.cache_ratio
    if ratio is not None:
        # Omitted rather than zeroed when unreported: a false 0.0 would drag SC-005 down with a
        # number nobody measured.
        derived["cache_ratio"] = round(ratio, 4)
    return derived


def _edit_to_dict(application: EditApplication) -> dict:
    payload = {
        "file": application.operation.file,
        "anchor_kind": application.operation.anchor_kind,
        "outcome": application.outcome.value,
        "relaxation_level": application.relaxation_level,
    }
    if application.outcome is ApplyOutcome.FAILED and application.failure_reason:
        payload["failure_reason"] = application.failure_reason
    return payload


def from_run(run_id: str, result: RunResult, project: Path, template_id: str = "") -> RunRecord:
    """Build a record from a completed pipeline run's attempts."""
    applications = [a for attempt in result.attempts for a in attempt.apply_report.applications]
    record = RunRecord(
        run_id=run_id,
        project_path=str(project),
        template_id=template_id,
        outcome=result.outcome.value,
        repair_attempts=_repairs_from(result),
        edit_applications=applications,
        retry_budget=result.budget,
        first_attempt_build_green=bool(result.attempts) and result.attempts[0].passed,
    )
    return record


def _repairs_from(result: RunResult) -> list[RepairAttempt]:
    """Every attempt after the first is a repair; the first is the initial write."""
    repairs: list[RepairAttempt] = []
    for index, attempt in enumerate(result.attempts[1:], start=1):
        previous = result.attempts[index - 1]
        repairs.append(
            RepairAttempt(
                attempt=index,
                classification=previous.verification.classification.value,
                diagnostic_ids=tuple(
                    sorted({d.id for d in previous.verification.diagnostics})
                ),
                resolved=attempt.passed,
            )
        )
    return repairs


def write(project: Path, record: RunRecord, provider_reported_usd: float | None = None) -> Path:
    """Persist the record. Returns the path so the caller can report it."""
    directory = project / RUNS_RELDIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record.run_id}.json"
    path.write_text(
        json.dumps(record.to_dict(provider_reported_usd), indent=2) + "\n", encoding="utf-8"
    )
    return path


def new_run_id(stamp: datetime | None = None) -> str:
    moment = stamp or datetime.now(UTC)
    return moment.strftime("%Y%m%dT%H%M%SZ")


