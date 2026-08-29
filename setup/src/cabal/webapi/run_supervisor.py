# -*- coding: utf-8 -*-
"""Detached-process run supervision: the live handle over a codegen/eval run and the
read-time reconciliation of its state against on-disk artifacts.

Per research.md R1, a run executes as a detached OS process rather than a `JobManager`
thread: `JobManager` is memory-only (`self._jobs = {}`, never rehydrated from storage)
and its work runs on daemon threads that die with the interpreter, while the Tauri shell
kills the backend it spawned on window close. Anything that must outlive either event --
an eval matrix is explicitly a multi-hour operation -- has to be a real OS process the
backend can find again, not a thread it owns. This module is where that supervision
lives: launching a detached process, tracking its handle, reconciling its presentation
state at read time, checking post-restart resource liveness, and cancelling it. Both
`codegen_service.py` and `evals_service.py` sit on top of it rather than managing
processes themselves, so the run-ownership model is decided exactly once (research.md R7).
Platform-specific spawn/kill mechanics live in the sibling `run_supervisor_process.py` --
this module owns what a run's state means, not how an OS process is started or killed.

`NotWiredError` is defined here rather than imported from `cabal.dotnetgen.exits` --
that one is a plain `Exception` built for the CLI's stdout/stderr dispatch contract. This
one subclasses the webapi `ApiError` so a not-yet-implemented surface fails through the
existing envelope exception handler exactly like any other expected API failure, never a
bare 500 -- which is what lets a read route stay honestly unwired without breaking the
zero-write GET sweep every `/api/*` route is already held to.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from cabal.webapi.envelope import ApiError, utc_now_iso
from cabal.webapi.run_supervisor_process import spawn_detached, terminate_by_pid
from cabal.webapi.security import is_pid_alive
from cabal.webapi.storage import Storage

RunKind = Literal["codegen.run", "evals.matrix"]
RunState = Literal["running", "succeeded", "failed", "cancelled", "interrupted"]

_CODEGEN_OUTCOME_STATES: Final[dict[str, RunState]] = {
    "completed": "succeeded",
    # A deliberate stop by the developer at the approval gate, not a failure (data-model A3).
    "rejected_at_gate": "cancelled",
    # Repairs exhausted: a genuine code defect the pipeline could not fix.
    "halted_at_ceiling": "failed",
    # A broken toolchain, not a code defect -- consumed zero retry budget.
    "aborted_environment": "failed",
}
ExclusiveResource = Literal["codegen", "evals"]
AvailabilityReason = Literal[
    "available",
    "no_project_selected",
    "not_a_dotnet_project",
    "subsystem_missing",
    "no_benchmark_tree",
    "definitions_invalid",
    "definitions_read_only",
]

# One level of subdirectories covers the common `src/<Project>/<Project>.csproj` layout
# without a full recursive walk of a possibly large existing tree.
_DOTNET_MARKER_GLOBS: tuple[str, ...] = ("*.sln", "*.csproj", "*/*.csproj")


class NotWiredError(ApiError):
    """Raised by a webapi surface whose implementation is scheduled in a later task.

    A 404 rather than a 500 is deliberate: the route is correctly wired into the app, it
    just has nothing behind it yet -- which is exactly what "not found" means to a caller
    reading this specific piece of data.
    """

    def __init__(self, surface: str, task: str) -> None:
        message = f"{surface!r} is not wired yet - implemented in {task}"
        super().__init__(404, "not_wired", message)
        self.surface = surface
        self.task = task


@dataclass(frozen=True)
class SupervisedRun:
    """The backend's live handle on a detached process (data-model B1).

    Ephemeral by design: everything durable about a run lives in its own artifact tree
    (`<project>/.dotnetgen/runs/<run-id>.json` or `evals/results/<run-id>/`). Losing this
    handle on a restart is expected and recoverable -- `reconcile_state` rebuilds the
    picture from `pid` liveness plus `artifact_root`, never from a second store. `pid`
    additionally survives a restart in `storage.supervised_runs`, purely so
    `check_resource_liveness` can find a still-live run again (T011); that row is
    bookkeeping about the handle, not a copy of run data.
    """

    job_id: str
    kind: RunKind
    run_id: str
    pid: int | None
    artifact_root: str
    exclusive_resource: ExclusiveResource


@dataclass(frozen=True)
class ModuleAvailability:
    """Why a module can or cannot operate right now (data-model B3).

    Feeds the existing `ModuleUnavailable` frontend placeholder (FR-002). `no_benchmark_tree`
    (a setup state with a next step) and `definitions_invalid` (an error) are deliberately
    distinct reasons -- collapsing them would tell a user to "set up" a tree that simply
    fails to validate, or hide a real validation failure behind a first-run prompt.
    """

    available: bool
    reason: AvailabilityReason
    detail: str = ""


def launch_detached(
    kind: RunKind,
    *,
    command: Sequence[str],
    cwd: Path | str,
    job_id: str,
    run_id: str,
    artifact_root: str,
    exclusive_resource: ExclusiveResource,
    storage: Storage,
    env: Mapping[str, str] | None = None,
    log_path: Path | None = None,
) -> SupervisedRun:
    """Spawn the detached OS process backing a run and return its live handle (T008).

    The process must survive backend exit (research.md R1) -- see
    `run_supervisor_process.spawn_detached` for how. The handle's `pid` is additionally
    persisted so a later restart's `check_resource_liveness` (T011) can find this run
    again once the in-memory `JobManager._resources` lock that guarded it is gone.
    """
    process = spawn_detached(command, cwd=cwd, env=env, log_path=log_path)
    run = SupervisedRun(
        job_id=job_id,
        kind=kind,
        run_id=run_id,
        pid=process.pid,
        artifact_root=str(artifact_root),
        exclusive_resource=exclusive_resource,
    )
    storage.save_supervised_run(_run_to_row(run))
    return run


def reconcile_state(run: SupervisedRun) -> RunState:
    """Derive a run's presentation state at read time; never persisted (research.md R2).

    Process alive -> running. Process gone with a complete artifact tree -> the
    artifacts' own recorded outcome. Process gone with an incomplete artifact tree ->
    interrupted, which stays a presentation state and is never written to the `jobs`
    table's state column (T010) -- `jobs.FinishState` has no `"interrupted"` member, so
    nothing in the existing job state machine could persist it even by mistake.
    Implemented in T009.
    """
    if run.pid is not None and is_pid_alive(run.pid):
        return "running"
    artifact_root = Path(run.artifact_root)
    if run.kind == "codegen.run":
        outcome = _codegen_recorded_outcome(artifact_root)
        if outcome is None:
            return "interrupted"
        return _CODEGEN_OUTCOME_STATES[outcome]
    return "succeeded" if _evals_matrix_complete(artifact_root) else "interrupted"


def presented_state(job_state: str, run: SupervisedRun) -> RunState:
    """Layer read-time reconciliation on top of a job's own stored state, without ever
    writing back (T010). Only a job the existing state machine still calls "running" --
    the stranded-row case research.md R2 describes, where the backend died before
    `JobManager.finish` ever ran -- needs reconciling; a job the state machine already
    finished (succeeded/failed/cancelled) is reported exactly as stored.
    """
    if job_state != "running":
        return job_state  # type: ignore[return-value]  # already one of the shared terminal states
    return reconcile_state(run)


def check_resource_liveness(
    exclusive_resource: ExclusiveResource, *, storage: Storage
) -> SupervisedRun | None:
    """Detect a still-live detached run after a restart, when the in-memory resource
    lock in `cabal.webapi.jobs.JobManager` has already been lost (research.md R7).

    `JobManager._resources` is memory-only, so a fresh backend process starts with no
    opinion at all about which resources are held; without this check, a second launch
    for the same module would race a still-running detached process from before the
    restart. Implemented in T011.
    """
    row = storage.load_supervised_run(exclusive_resource)
    if row is None:
        return None
    run = _row_to_run(row)
    if run.pid is not None and is_pid_alive(run.pid):
        return run
    storage.delete_supervised_run(exclusive_resource)
    return None


def cancel(
    run: SupervisedRun,
    *,
    storage: Storage,
    worktrees: Sequence[tuple[Path, Path]] = (),
) -> None:
    """Terminate a run's process tree and release its durable resource handle (T013).

    Reuses `cabal.evals.proc.kill_process_tree`: a plain kill of the root pid would
    orphan whatever the run itself spawned (an eval cell's agent subprocess, a dotnetgen
    provider call). `worktrees` is `(repo, dest)` pairs the caller (the service that
    knows which cells were in flight, from the run's own manifest) wants cleaned up --
    a killed cell's own `finally` block never runs, so its worktree would otherwise be
    orphaned on disk. Best-effort: a worktree git already can't remove is not fatal to
    cancellation itself; full worktree discovery for a run this backend did not launch
    this session is `evals.worktree_cleanup` (T077, Phase 10), not this function's job.
    """
    if run.pid is not None:
        terminate_by_pid(run.pid)
    if worktrees:
        from cabal.evals import worktree as evals_worktree

        for repo, dest in worktrees:
            try:
                evals_worktree.remove_worktree(repo, dest)
            except evals_worktree.WorktreeError:
                pass
    storage.delete_supervised_run(run.exclusive_resource)


def probe_codegen_availability(project: Path | None) -> ModuleAvailability:
    """Data-model B3, codegen column. Ordered so the cheapest, most decisive checks run
    first: no project at all, then "is this even a .NET tree" (before the user writes a
    request), then whether the wrapped subsystem itself imports.
    """
    if project is None:
        return ModuleAvailability(False, "no_project_selected")
    project = Path(project)
    if not any(any(project.glob(pattern)) for pattern in _DOTNET_MARKER_GLOBS):
        return ModuleAvailability(False, "not_a_dotnet_project")
    try:
        import cabal.dotnetgen.pipeline  # noqa: F401
    except ImportError as exc:
        return ModuleAvailability(False, "subsystem_missing", detail=str(exc))
    return ModuleAvailability(True, "available")


def _codegen_decided_outcomes() -> frozenset[str]:
    """The run-record `outcome` enum has exactly these four values
    (contracts/run-record.schema.json via `cabal.dotnetgen.pipeline.RunOutcome`).

    "Decided" is not the same as "succeeded": only `completed` is success. A run that
    ended `aborted_environment` or `halted_at_ceiling` finished writing its record and is
    therefore not interrupted, but reporting either as succeeded would erase the very
    distinction FR-017 and SC-005 exist to preserve -- a broken toolchain must never read
    as a working build. `_CODEGEN_OUTCOME_STATES` does that mapping; the finer four-way
    detail is read from the record itself by codegen_service.py (T017). Imported lazily
    (like the availability probes above) so this module stays importable even where
    `cabal.dotnetgen` is not installed.
    """
    from cabal.dotnetgen.pipeline import RunOutcome

    return frozenset(member.value for member in RunOutcome)


def probe_evals_availability(project: Path | None) -> ModuleAvailability:
    """Data-model B3, evals column. `no_benchmark_tree` (no `evals/` directory yet) is a
    setup state with a next step; `definitions_invalid` (the directory exists but fails
    validation) is an error blocking launch (FR-031) -- keeping them distinct is the
    point of T014, per data-model B3's own warning against collapsing them.
    """
    if project is None:
        return ModuleAvailability(False, "no_project_selected")
    try:
        from cabal.evals.definitions import validate_tree
    except ImportError as exc:
        return ModuleAvailability(False, "subsystem_missing", detail=str(exc))
    evals_root = Path(project) / "evals"
    if not evals_root.is_dir():
        return ModuleAvailability(False, "no_benchmark_tree")
    errors = validate_tree(evals_root)
    if errors:
        detail = "; ".join(f"{error.file}: {error.field}: {error.message}" for error in errors)
        return ModuleAvailability(False, "definitions_invalid", detail=detail)
    return ModuleAvailability(True, "available")


def _codegen_recorded_outcome(record_path: Path) -> str | None:
    """The run-record's own `outcome`, or None when the record is absent, unparseable, or
    carries no decided outcome -- which is what "interrupted" means for a codegen run.
    `artifact_root` for a `codegen.run` kind is the record file itself
    (`.dotnetgen/runs/<run-id>.json`), not a directory.
    """
    try:
        payload = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    outcome = payload.get("outcome")
    return outcome if outcome in _codegen_decided_outcomes() else None


def _evals_matrix_complete(run_dir: Path) -> bool:
    """A matrix run is "complete" once every cell its own manifest promised has a
    parseable `metrics.json` (`cabal.evals.matrix.is_cell_complete`) -- reusing the
    subsystem's own resume rule rather than maintaining a second, divergent opinion
    about progress (research.md R2, data-model A5).
    """
    from cabal.evals import matrix

    manifest_path = run_dir / matrix.MANIFEST_FILENAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    tasks = manifest.get("tasks")
    runs = manifest.get("runs")
    baseline = manifest.get("baseline")
    candidate = manifest.get("candidate")
    if not isinstance(tasks, list) or not isinstance(runs, int):
        return False
    if not isinstance(baseline, str) or not isinstance(candidate, str):
        return False
    for task_id in tasks:
        for profile_name in (baseline, candidate):
            for repetition in range(1, runs + 1):
                cell_dir = run_dir / str(task_id) / profile_name / str(repetition)
                if not matrix.is_cell_complete(cell_dir):
                    return False
    return True


def _run_to_row(run: SupervisedRun) -> dict:
    return {
        "exclusive_resource": run.exclusive_resource,
        "job_id": run.job_id,
        "kind": run.kind,
        "run_id": run.run_id,
        "pid": run.pid,
        "artifact_root": run.artifact_root,
        "created_at": utc_now_iso(),
    }


def _row_to_run(row: dict) -> SupervisedRun:
    return SupervisedRun(
        job_id=row["job_id"],
        kind=row["kind"],
        run_id=row["run_id"],
        pid=row["pid"],
        artifact_root=row["artifact_root"],
        exclusive_resource=row["exclusive_resource"],
    )
