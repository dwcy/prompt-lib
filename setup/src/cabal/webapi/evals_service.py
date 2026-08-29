# -*- coding: utf-8 -*-
"""Read surface over the evals subsystem's own artifacts (run history, the A/B report,
per-cell detail, and worktree listing).

`cabal.evals` has no `--json` mode (research.md R5, recorded as a finding against
019-agent-eval-harness), so every read here comes from `evals/results/<run-id>/`
(manifest, per-cell metrics/comparison, report) or a direct call into the package's own
reducer -- never from parsing CLI stdout. Aggregation rules (sample counts, stddev
cutoffs, excluded pairs) belong to that reducer alone; this module must not re-derive
them (data-model A8, SC-010). Definition authoring lives in
`evals_definitions_service.py`; mutations that need the confirmation gate (launch,
cancel, resume, worktree cleanup) live in `actions_catalog/evals.py`.
"""

from __future__ import annotations

from pathlib import Path

from cabal.webapi.run_supervisor import ModuleAvailability, NotWiredError


def probe_availability(project: Path | None) -> ModuleAvailability:
    """Why the evals module can or cannot operate right now (data-model B3).

    `no_benchmark_tree` (a setup state) and `definitions_invalid` (an error) must stay
    distinct values (spec edge case). Implemented in T014.
    """
    raise NotWiredError("evals_service.probe_availability", "T014")


def list_runs(project: Path) -> list[dict]:
    """Run history from `evals/results/`, newest first, reconciled at read time.

    Includes runs the CLI produced outside the workspace -- there is no "launched here"
    flag (FR-045). A partially written run directory yields a `"readable": false` entry
    rather than breaking the listing. Implemented in T031.
    """
    raise NotWiredError("evals_service.list_runs", "T031")


def get_report(project: Path, run_id: str) -> dict:
    """The A/B comparison, served from the subsystem's own reducer (data-model A8).

    Every aggregate carries its sample count `n` (SC-009); the deterministic half of the
    report is still returned when judge results are absent (FR-043). Implemented in
    T032 and T034.
    """
    raise NotWiredError("evals_service.get_report", "T032")


def get_cell_detail(project: Path, run_id: str, task: str, profile: str, repetition: int) -> dict:
    """One cell's check outcomes and agent metrics (FR-042).

    A timed-out check is a result carrying a timeout flag, never an error (data-model A6).
    Implemented in T033.
    """
    raise NotWiredError("evals_service.get_cell_detail", "T033")


def list_worktrees(project: Path) -> list[dict]:
    """Temporary worktrees on disk, including orphans left by a crashed run (FR-044).

    Implemented in T077.
    """
    raise NotWiredError("evals_service.list_worktrees", "T077")
