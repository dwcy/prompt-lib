# -*- coding: utf-8 -*-
"""Read surface over the dotnetgen subsystem's own artifacts: run history, a run's
per-stage cost, the pending approval-gate intent, and stage->provider bindings.

Owns nothing: `.dotnetgen/runs/<run-id>.json` and the pending-intent file are read
verbatim from `cabal.dotnetgen` per research.md R5 (direct import, no subprocess, no
stdout parsing) and never copied into SQLite (data-model cross-cutting rule 1) -- a
workspace-launched run and a CLI-launched run must be the exact same read path (FR-045).
Mutations (`codegen.plan`/`approve`/`reject`/`new_service`) live in
`actions_catalog/codegen.py`, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cabal.webapi.run_supervisor import ModuleAvailability, NotWiredError


@dataclass(frozen=True)
class StageBinding:
    """Current stage -> provider/model mapping, for the bindings view (US7, data-model B2).

    `is_local` must be asked of the provider instance, never inferred from its name --
    a name-based guess would report a hosted run as free.
    """

    stage: str
    provider: str
    model: str
    is_local: bool
    reachable: bool


def probe_availability(project: Path | None) -> ModuleAvailability:
    """Why the codegen module can or cannot operate right now (data-model B3).

    Implemented in T014: distinguishes `no_project_selected`, `not_a_dotnet_project`,
    and `subsystem_missing` per `contracts/codegen-api.md`.
    """
    raise NotWiredError("codegen_service.probe_availability", "T014")


def list_runs(project: Path) -> list[dict]:
    """Run history from `<project>/.dotnetgen/runs/`, newest first.

    A malformed run record must yield a `"readable": false` entry rather than fail the
    whole listing (spec edge case, data-model A1). Implemented in T017.
    """
    raise NotWiredError("codegen_service.list_runs", "T017")


def get_run(project: Path, run_id: str) -> dict:
    """One run: request, template, outcome, per-stage costs, retry budget.

    Every pipeline stage appears, including ones that did not run, with explicit zeros
    (FR-018); `priced: false` and unreported cache figures stay distinguishable from a
    real zero (FR-008, data-model A2). Implemented in T017.
    """
    raise NotWiredError("codegen_service.get_run", "T017")


def get_pending_intent(project: Path) -> dict | None:
    """The pending intent awaiting a decision at the approval gate, or None.

    `stale` is computed at read time against `cabal.dotnetgen.intent.solution_fingerprint`,
    never cached (research.md R3). Implemented in T017.
    """
    raise NotWiredError("codegen_service.get_pending_intent", "T017")


def stage_cost_breakdown(project: Path, run_id: str) -> dict:
    """Total, initial-vs-repair split, and largest-spending stage for one run (SC-004).

    Derived at read time from the run record; nothing here is stored. Implemented in T051.
    """
    raise NotWiredError("codegen_service.stage_cost_breakdown", "T051")


def list_stage_bindings() -> list[StageBinding]:
    """Every pipeline stage's current provider/model binding and reachability.

    Implemented in T072.
    """
    raise NotWiredError("codegen_service.list_stage_bindings", "T072")
