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

import json
from pathlib import Path

from cabal.evals import judge as evals_judge
from cabal.evals import matrix as evals_matrix
from cabal.evals import report as evals_report
from cabal.webapi.envelope import ApiError
from cabal.webapi.run_supervisor import (
    ModuleAvailability,
    NotWiredError,
    SupervisedRun,
    check_resource_liveness,
    probe_evals_availability,
    reconcile_state,
)
from cabal.webapi.storage import Storage

_REQUIRED_MANIFEST_KEYS = ("run_id", "baseline", "candidate", "runs", "tasks")


def probe_availability(project: Path | None) -> ModuleAvailability:
    """Why the evals module can or cannot operate right now (data-model B3).

    Delegates to `run_supervisor.probe_evals_availability` (T014), which already keeps
    `no_benchmark_tree` (a setup state) and `definitions_invalid` (an error) distinct.
    """
    return probe_evals_availability(project)


def _results_dir(project: Path) -> Path:
    return Path(project) / "evals" / "results"


def _require_project(project: Path | None) -> Path:
    if project is None:
        raise ApiError(404, "run_not_found", "select a project before reading eval runs")
    return Path(project)


def _manifest_well_formed(manifest: dict) -> bool:
    if not all(key in manifest for key in _REQUIRED_MANIFEST_KEYS):
        return False
    return isinstance(manifest.get("tasks"), list) and isinstance(manifest.get("runs"), int)


def list_runs(project: Path | None, *, storage: Storage) -> list[dict]:
    """Run history from `evals/results/`, newest first, reconciled at read time.

    Includes runs the CLI produced outside the workspace -- there is no "launched here"
    flag, because there is no separate code path (FR-045). A partially written run
    directory yields a `"readable": false` entry rather than breaking the listing.
    `resumable` is derived from the manifest alone (research.md R2), never from a job
    row: only the one run this backend's own `check_resource_liveness` still finds alive
    for the `"evals"` resource is ever reported `"running"`; every other entry -- CLI-run
    or not -- is reconciled purely from its own artifact tree via `reconcile_state`,
    reused rather than reimplemented so a workspace read and `python -m cabal.evals
    report` can never silently disagree (SC-010). No project selected is an empty
    history, not an error -- the zero-write GET sweep exercises every read route with no
    project selected and expects a clean 200/404/422, never a 500.
    """
    if project is None:
        return []
    results_dir = _results_dir(project)
    if not results_dir.is_dir():
        return []

    live_run = check_resource_liveness("evals", storage=storage)
    entries: list[dict] = []
    for run_dir in sorted(results_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        run_id = run_dir.name
        manifest_path = run_dir / evals_matrix.MANIFEST_FILENAME
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            entries.append({"run_id": run_id, "readable": False, "error": str(exc)})
            continue
        if not isinstance(manifest, dict):
            entries.append(
                {"run_id": run_id, "readable": False, "error": "run manifest is not a JSON object"}
            )
            continue

        pid = live_run.pid if live_run is not None and live_run.run_id == run_id else None
        synthetic = SupervisedRun(
            job_id=live_run.job_id if pid is not None else "",
            kind="evals.matrix",
            run_id=run_id,
            pid=pid,
            artifact_root=str(run_dir),
            exclusive_resource="evals",
        )
        state = reconcile_state(synthetic)
        entries.append(
            {
                "run_id": run_id,
                "state": state,
                "resumable": state == "interrupted" and _manifest_well_formed(manifest),
                "baseline": manifest.get("baseline"),
                "candidate": manifest.get("candidate"),
                "tasks": manifest.get("tasks"),
                "runs": manifest.get("runs"),
                "adapter": manifest.get("adapter"),
                "created_at": manifest.get("created_at"),
            }
        )
    return entries


def _excluded_pairs_tally(run_dir: Path, tasks: list) -> dict[str, int]:
    """How many judged pairs `report.py`'s own `pairwise_win_rate` silently excludes, and
    why (FR-039) -- a count, not an aggregate: the win-rate mean/n themselves always come
    from `evals_report.build_report` untouched (SC-010); this only tallies `winner`
    values the reducer already reads but does not surface a reason for.
    """
    total = tie = judge_error = 0
    for task_id in tasks:
        path = run_dir / str(task_id) / evals_judge.COMPARISON_FILENAME
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pairs = data.get("pairs") if isinstance(data, dict) else None
        for pair in pairs if isinstance(pairs, list) else []:
            winner = pair.get("winner") if isinstance(pair, dict) else None
            if winner == "tie":
                tie += 1
                total += 1
            elif winner == "judge_error":
                judge_error += 1
                total += 1
    return {"total": total, "tie": tie, "judge_error": judge_error}


def get_report(project: Path | None, run_id: str) -> dict:
    """The A/B comparison, served from the subsystem's own reducer (data-model A8).

    Every aggregate carries its sample count `n` (SC-009); the deterministic half of the
    report is still returned when judge results are absent (FR-043), since
    `evals_report.build_report` already computes every non-judge metric independently of
    whether any `comparison.json` exists. The only addition on top of the reducer's own
    payload is `excluded_pairs` on the `pairwise_win_rate` row (FR-039) -- the reducer
    tallies decisive wins but never reports how many pairs it excluded or why.
    """
    run_dir = _results_dir(_require_project(project)) / run_id
    try:
        bundle = evals_report.build_report(run_dir)
    except evals_report.ReportError as exc:
        raise ApiError(404, "run_not_found", str(exc)) from exc

    payload = dict(bundle.payload)
    tasks = payload.get("tasks", [])
    tally = _excluded_pairs_tally(run_dir, tasks)
    metrics_rows = []
    for row in payload.get("metrics_rows", []):
        row = dict(row)
        if row.get("metric") == "pairwise_win_rate":
            row["excluded_pairs"] = tally
        metrics_rows.append(row)
    payload["metrics_rows"] = metrics_rows
    return payload


def get_cell_detail(
    project: Path | None, run_id: str, task: str, profile: str, repetition: int
) -> dict:
    """One cell's check outcomes and agent metrics (FR-042).

    A timed-out check is a result carrying a timeout flag, never an error (data-model
    A6): `metrics.json` already records it that way, so this is a direct read.
    """
    cell_dir = _results_dir(_require_project(project)) / run_id / task / profile / str(repetition)
    path = cell_dir / evals_matrix.METRICS_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ApiError(404, "cell_not_found", f"no readable cell metrics at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ApiError(404, "cell_not_found", f"cell metrics at {path} is not a JSON object")
    return payload


def list_worktrees(project: Path) -> list[dict]:
    """Temporary worktrees on disk, including orphans left by a crashed run (FR-044).

    Implemented in T077.
    """
    raise NotWiredError("evals_service.list_worktrees", "T077")
