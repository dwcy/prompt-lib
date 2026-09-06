# -*- coding: utf-8 -*-
"""Read back recorded runs and render what they cost.

The ledger writes; this reads. Kept apart because reporting has no business being able to change
a record, and because `report` must work against runs written by an older version of the pipeline.

The rendering answers the four cost-centre question the feature opened with - output tokens, input
tokens, round trips, retries - rather than printing a single total. A single total cannot tell you
whether a run was expensive because the writing model is pricey or because it repaired three times,
and those have opposite fixes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cabal.dotnetgen.ledger import RUNS_RELDIR

_UNRECONCILED_NOTE: Final[str] = (
    "  ! cost could not be reconciled with provider-reported usage - treat as an estimate"
)


@dataclass(frozen=True)
class StoredRun:
    """One run record read from disk, as written."""

    run_id: str
    payload: dict

    @property
    def outcome(self) -> str:
        return str(self.payload.get("outcome", "unknown"))

    @property
    def total_cost_usd(self) -> float:
        stages = self.payload.get("stage_costs") or {}
        return sum(float(s.get("cost_usd", 0) or 0) for s in stages.values())

    @property
    def derived(self) -> dict:
        return self.payload.get("derived") or {}

    def render(self) -> str:
        lines = [f"run {self.run_id}  [{self.outcome}]"]
        for stage, cost in sorted((self.payload.get("stage_costs") or {}).items()):
            lines.append(
                f"  {stage:<10} {cost.get('provider', '?')}/{cost.get('model', '?')}"
                f"  in {cost.get('input_tokens', 0):>7}"
                f"  cached {cost.get('cached_input_tokens', 0):>7}"
                f"  out {cost.get('output_tokens', 0):>7}"
                f"  ${float(cost.get('cost_usd', 0) or 0):.4f}"
            )
        lines.append(f"  {'total':<10} ${self.total_cost_usd:.4f}")

        derived = self.derived
        repairs = self.payload.get("repair_attempts") or []
        budget = self.payload.get("retry_budget") or {}
        lines.append(
            f"  repairs    {budget.get('consumed', 0)}/{budget.get('ceiling', '?')}"
            f" ({len(repairs)} recorded)"
            f"  costing ${float(derived.get('repair_cost_usd', 0) or 0):.4f}"
            f" of ${self.total_cost_usd:.4f}"
        )
        if "cache_ratio" in derived:
            lines.append(f"  cache      {float(derived['cache_ratio']):.0%} of input served")
        else:
            lines.append("  cache      not reported by this provider")
        lines.append(
            f"  edits      {float(derived.get('edit_success_rate', 0)):.0%} applied first time"
            f"; first-attempt build green: {bool(derived.get('first_attempt_build_green'))}"
        )
        if not derived.get("reconciled", False):
            lines.append(_UNRECONCILED_NOTE)
        return "\n".join(lines)


def load_runs(project: Path) -> tuple[StoredRun, ...]:
    """Every recorded run, newest last. Unreadable records are skipped, never fatal."""
    directory = project / RUNS_RELDIR
    if not directory.is_dir():
        return ()
    runs: list[StoredRun] = []
    for path in sorted(directory.glob("*.json")):
        try:
            runs.append(StoredRun(path.stem, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError):
            continue
    return tuple(runs)


def select(runs: tuple[StoredRun, ...], *, run_id: str | None, last: int | None) -> tuple[StoredRun, ...]:
    """Apply `--run` / `--last`. With neither, the most recent run is the useful default."""
    if run_id is not None:
        return tuple(r for r in runs if r.run_id == run_id)
    if last is not None:
        return runs[-last:] if last > 0 else ()
    return runs[-1:]


def summarise(runs: tuple[StoredRun, ...]) -> dict:
    """Aggregate across runs. SC-005 is a property of a sequence, not of any single run."""
    if not runs:
        return {"runs": 0}
    completed = [r for r in runs if r.outcome == "completed"]
    ratios = [
        float(r.derived["cache_ratio"]) for r in runs if "cache_ratio" in r.derived
    ]
    greens = [bool(r.derived.get("first_attempt_build_green")) for r in runs]
    return {
        "runs": len(runs),
        "completed": len(completed),
        "total_cost_usd": round(sum(r.total_cost_usd for r in runs), 6),
        "repair_cost_usd": round(
            sum(float(r.derived.get("repair_cost_usd", 0) or 0) for r in runs), 6
        ),
        # Omitted rather than zeroed when nothing reported caching - see the ledger's note.
        "mean_cache_ratio": round(sum(ratios) / len(ratios), 4) if ratios else None,
        "first_attempt_build_green_rate": round(sum(greens) / len(greens), 4) if greens else None,
        "unreconciled": sum(1 for r in runs if not r.derived.get("reconciled", False)),
    }


def render(runs: tuple[StoredRun, ...]) -> str:
    if not runs:
        return "no runs recorded yet - run `apply` first"
    blocks = [run.render() for run in runs]
    if len(runs) > 1:
        totals = summarise(runs)
        ratio = totals["mean_cache_ratio"]
        blocks.append(
            f"across {totals['runs']} runs: ${totals['total_cost_usd']:.4f} total, "
            f"${totals['repair_cost_usd']:.4f} on repairs, "
            + (f"{ratio:.0%} mean cache" if ratio is not None else "cache not reported")
        )
    return "\n\n".join(blocks)
