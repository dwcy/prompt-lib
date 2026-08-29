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

`NotWiredError` is defined here rather than imported from `cabal.dotnetgen.exits` --
that one is a plain `Exception` built for the CLI's stdout/stderr dispatch contract. This
one subclasses the webapi `ApiError` so a not-yet-implemented surface fails through the
existing envelope exception handler exactly like any other expected API failure, never a
bare 500 -- which is what lets a read route stay honestly unwired without breaking the
zero-write GET sweep every `/api/*` route is already held to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cabal.webapi.envelope import ApiError

RunKind = Literal["codegen.run", "evals.matrix"]
RunState = Literal["running", "succeeded", "failed", "cancelled", "interrupted"]
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
    picture from `pid` liveness plus `artifact_root`, never from a second store.
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


def launch_detached(kind: RunKind, *, artifact_root: str) -> SupervisedRun:
    """Spawn the detached OS process backing a run and return its live handle.

    Implemented in T008: the process must survive backend exit (research.md R1).
    """
    raise NotWiredError("run_supervisor.launch_detached", "T008")


def reconcile_state(run: SupervisedRun) -> RunState:
    """Derive a run's presentation state at read time; never persisted (research.md R2).

    Process alive -> running. Process gone with a complete artifact tree -> the
    artifacts' own recorded outcome. Process gone with an incomplete artifact tree ->
    interrupted, which stays a presentation state and is never written to the `jobs`
    table's state column (T010). Implemented in T009.
    """
    raise NotWiredError("run_supervisor.reconcile_state", "T009")


def check_resource_liveness(exclusive_resource: ExclusiveResource) -> SupervisedRun | None:
    """Detect a still-live detached run after a restart, when the in-memory resource
    lock in `cabal.webapi.jobs.JobManager` has already been lost.

    Implemented in T011, per research.md R7.
    """
    raise NotWiredError("run_supervisor.check_resource_liveness", "T011")


def cancel(run: SupervisedRun) -> None:
    """Terminate a run's process tree and clean up its temporary worktrees.

    Implemented in T013, reusing `cabal.evals.proc.kill_process_tree`.
    """
    raise NotWiredError("run_supervisor.cancel", "T013")
