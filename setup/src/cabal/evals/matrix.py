# -*- coding: utf-8 -*-
"""Matrix engine: task x profile x N cells with atomic metrics writes, resume, and failure isolation.

Per FR-011/FR-012: every cell writes its metrics.json atomically at completion (a parseable
metrics.json marks the cell complete and resume skips it), and a failing cell records its
machine-readable reason then lets the matrix continue — one bad cell never aborts the run.
"""

from __future__ import annotations

import json
import os
import tempfile
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal

from cabal.evals import checks, metrics, profile, worktree
from cabal.evals.adapters.base import (
    AdapterUnavailableError,
    AgentAdapter,
    AgentRunResult,
    AgentRunSpec,
)
from cabal.evals.definitions_model import ConfigProfile, EvalConfig, Task
from cabal.evals.metrics import TranscriptMetrics

RUN_ID_PREFIX: Final[str] = "evalrun-"
MANIFEST_FILENAME: Final[str] = "run.json"
METRICS_FILENAME: Final[str] = "metrics.json"
TRANSCRIPT_FILENAME: Final[str] = "transcript.jsonl"
PATCH_FILENAME: Final[str] = "patch.diff"
OUTPUT_FILENAME: Final[str] = "output.txt"

FAILURE_WORKTREE: Final[str] = "worktree_error"
FAILURE_PROFILE: Final[str] = "profile_error"
FAILURE_ADAPTER_UNAVAILABLE: Final[str] = "adapter_unavailable"

CellStatus = Literal["completed", "failed", "skipped"]


class _CellError(Exception):
    """Stage-tagged cell failure; `reason` is one of the metrics.schema.json failure values."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason


@dataclass(frozen=True)
class CellResult:
    """Outcome of one (task, config, repetition) cell after this invocation."""

    task_id: str
    config_name: str
    repetition: int
    status: CellStatus
    failure_reason: str | None


@dataclass(frozen=True)
class MatrixSummary:
    """What the CLI reports after a matrix pass."""

    run_id: str
    run_dir: Path
    completed: int
    failed: int
    skipped: int
    cells: tuple[CellResult, ...]


def mint_run_id() -> str:
    return datetime.now(UTC).strftime(f"{RUN_ID_PREFIX}%Y%m%dT%H%M%SZ")


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_cell_complete(cell_dir: Path) -> bool:
    """Resume rule: a cell with a parseable metrics.json is complete and never re-run."""
    path = Path(cell_dir) / METRICS_FILENAME
    if not path.is_file():
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return True


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write via .tmp + os.replace so an interruption never leaves a half-written artifact."""
    path = Path(path)
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def run_matrix(
    eval_config: EvalConfig,
    tasks: Sequence[Task],
    baseline_profile: ConfigProfile,
    candidate_profile: ConfigProfile,
    runs: int,
    results_dir: Path,
    adapter: AgentAdapter,
    resume_run_id: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> MatrixSummary:
    """Execute (or resume) the full matrix; per-cell failures are recorded, never propagated."""
    run_id = resume_run_id or mint_run_id()
    run_dir = Path(results_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_manifest(run_dir, run_id, tasks, baseline_profile, candidate_profile, runs, adapter)
    if _profiles_identical(baseline_profile, candidate_profile):
        warnings.warn(
            f"no-op comparison: profiles {baseline_profile.name!r} and "
            f"{candidate_profile.name!r} are byte-identical",
            stacklevel=2,
        )
    cells: list[CellResult] = []
    for task in tasks:
        for prof in (baseline_profile, candidate_profile):
            for repetition in range(1, runs + 1):
                cell = _run_cell(task, prof, repetition, run_id, run_dir, eval_config, adapter)
                cells.append(cell)
                if progress is not None:
                    progress(_progress_line(cell))
    return MatrixSummary(
        run_id=run_id,
        run_dir=run_dir,
        completed=sum(1 for cell in cells if cell.status == "completed"),
        failed=sum(1 for cell in cells if cell.status == "failed"),
        skipped=sum(1 for cell in cells if cell.status == "skipped"),
        cells=tuple(cells),
    )


def _progress_line(cell: CellResult) -> str:
    suffix = f" ({cell.failure_reason})" if cell.failure_reason else ""
    return f"{cell.task_id}/{cell.config_name}/{cell.repetition}: {cell.status}{suffix}"


def _write_manifest(
    run_dir: Path,
    run_id: str,
    tasks: Sequence[Task],
    baseline: ConfigProfile,
    candidate: ConfigProfile,
    runs: int,
    adapter: AgentAdapter,
) -> None:
    """Persisted so `run --resume <id>` can restore profile/task/runs selection without re-flagging."""
    path = run_dir / MANIFEST_FILENAME
    if path.is_file():
        return
    write_json_atomic(
        path,
        {
            "run_id": run_id,
            "baseline": baseline.name,
            "candidate": candidate.name,
            "runs": runs,
            "tasks": [task.id for task in tasks],
            "adapter": adapter.name,
            "created_at": _utc_now(),
        },
    )


def _profiles_identical(baseline: ConfigProfile, candidate: ConfigProfile) -> bool:
    scratch = Path(tempfile.mkdtemp(prefix="cabal-evals-cmp-"))
    try:
        a = profile.materialize(baseline, scratch / "a", scratch / "a-wt")
        b = profile.materialize(candidate, scratch / "b", scratch / "b-wt")
        return profile.profiles_identical(a, b)
    except OSError:
        return False
    finally:
        profile.cleanup(scratch)


def _run_cell(
    task: Task,
    prof: ConfigProfile,
    repetition: int,
    run_id: str,
    run_dir: Path,
    eval_config: EvalConfig,
    adapter: AgentAdapter,
) -> CellResult:
    cell_dir = run_dir / task.id / prof.name / str(repetition)
    if is_cell_complete(cell_dir):
        return CellResult(task.id, prof.name, repetition, "skipped", None)
    cell_dir.mkdir(parents=True, exist_ok=True)
    started_at = _utc_now()
    scratch = Path(tempfile.mkdtemp(prefix="cabal-evals-"))
    worktree_path: Path | None = None
    result: AgentRunResult | None = None
    diff: worktree.DiffResult | None = None
    transcript = TranscriptMetrics()
    try:
        try:
            worktree_path = worktree.create_worktree(task.repo, task.ref, scratch / "wt")
        except worktree.WorktreeError as exc:
            raise _CellError(FAILURE_WORKTREE, str(exc)) from exc
        try:
            materialized = profile.materialize(prof, scratch, worktree_path)
        except OSError as exc:
            raise _CellError(FAILURE_PROFILE, str(exc)) from exc
        spec = AgentRunSpec(
            prompt=task.prompt,
            worktree=worktree_path,
            config_dir=materialized.config_dir,
            settings_file=materialized.settings_file,
            env=materialized.env,
            model=eval_config.agent_model,
            timeout_seconds=task.timeout_seconds or eval_config.run_timeout_seconds,
            skip_permissions=task.skip_permissions,
            transcript_path=cell_dir / TRANSCRIPT_FILENAME,
        )
        try:
            result = adapter.run(spec)
        except AdapterUnavailableError as exc:
            raise _CellError(FAILURE_ADAPTER_UNAVAILABLE, str(exc)) from exc
        try:
            diff = worktree.collect_diff(worktree_path)
            (cell_dir / PATCH_FILENAME).write_text(diff.patch_text, encoding="utf-8")
            (cell_dir / OUTPUT_FILENAME).write_text(result.final_text, encoding="utf-8")
        except (worktree.WorktreeError, OSError) as exc:
            raise _CellError(FAILURE_WORKTREE, str(exc)) from exc
        # Checks run only when the agent itself finished (data-model Run state machine: a check
        # timing out is a recorded check outcome, not a run failure) — failed runs keep checks: [].
        check_results: list[checks.CheckResult] = []
        if result.status == "completed":
            check_results = checks.run_checks(
                task, worktree_path, eval_config.check_timeout_seconds
            )
        transcript = metrics.parse_transcript(spec.transcript_path)
        payload = metrics.build_metrics(
            run_id=run_id,
            task_id=task.id,
            config_name=prof.name,
            repetition=repetition,
            adapter_name=adapter.name,
            status=result.status,
            failure_reason=result.failure_reason,
            wall_seconds=result.wall_seconds,
            started_at=started_at,
            finished_at=_utc_now(),
            capabilities=adapter.capabilities(),
            transcript=transcript,
            diff=diff,
            expected_files=task.expected_files,
            checks=check_results,
        )
        write_json_atomic(cell_dir / METRICS_FILENAME, payload)
        return CellResult(task.id, prof.name, repetition, result.status, result.failure_reason)
    except Exception as exc:
        # metrics.schema.json pins the failure enum, so unclassified harness errors file under
        # worktree_error rather than inventing a value the schema would reject.
        reason = exc.reason if isinstance(exc, _CellError) else FAILURE_WORKTREE
        _record_failed_cell(
            cell_dir, run_id, task, prof, repetition, adapter, reason, started_at,
            result, diff, transcript,
        )
        return CellResult(task.id, prof.name, repetition, "failed", reason)
    finally:
        if worktree_path is not None:
            try:
                worktree.remove_worktree(task.repo, worktree_path)
            except worktree.WorktreeError:
                warnings.warn(f"could not remove worktree {worktree_path}", stacklevel=2)
        profile.cleanup(scratch)


def _record_failed_cell(
    cell_dir: Path,
    run_id: str,
    task: Task,
    prof: ConfigProfile,
    repetition: int,
    adapter: AgentAdapter,
    reason: str,
    started_at: str,
    result: AgentRunResult | None,
    diff: worktree.DiffResult | None,
    transcript: TranscriptMetrics,
) -> None:
    """A failed run still writes metrics.json so the matrix stays resumable and countable."""
    payload = metrics.build_metrics(
        run_id=run_id,
        task_id=task.id,
        config_name=prof.name,
        repetition=repetition,
        adapter_name=adapter.name,
        status="failed",
        failure_reason=reason,
        wall_seconds=result.wall_seconds if result is not None else 0.0,
        started_at=started_at,
        finished_at=_utc_now(),
        capabilities=adapter.capabilities(),
        transcript=transcript,
        diff=diff,
        expected_files=task.expected_files,
    )
    try:
        write_json_atomic(cell_dir / METRICS_FILENAME, payload)
    except OSError:
        warnings.warn(f"could not record failed cell {cell_dir}", stacklevel=2)
