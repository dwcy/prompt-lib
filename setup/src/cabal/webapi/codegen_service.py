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

import json
from dataclasses import dataclass
from pathlib import Path

from cabal.dotnetgen import intent as dotnetgen_intent
from cabal.dotnetgen import ledger
from cabal.dotnetgen.providers.config import MODEL_STAGES
from cabal.webapi.envelope import ApiError
from cabal.webapi.run_supervisor import ModuleAvailability, NotWiredError, probe_codegen_availability

_CANONICAL_STAGES: tuple[str, ...] = (*MODEL_STAGES, "verify")
_ZERO_STAGE_COST: dict = {
    "provider": "",
    "model": "",
    "input_tokens": 0,
    "output_tokens": 0,
    "cost_usd": 0.0,
    "wall_clock_seconds": 0.0,
}


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

    Delegates to `run_supervisor.probe_codegen_availability` (T014), which already
    distinguishes `no_project_selected`, `not_a_dotnet_project`, and `subsystem_missing`
    per `contracts/codegen-api.md` -- this is just the service-layer seam the router
    calls, kept a thin wrapper so read and mutation paths share one availability opinion.
    """
    return probe_codegen_availability(project)


def list_runs(project: Path | None) -> list[dict]:
    """Run history from `<project>/.dotnetgen/runs/`, newest first.

    A malformed run record yields a `"readable": false` entry rather than fail the whole
    listing (spec edge case, data-model A1). Run ids are timestamp-formatted
    (`ledger.new_run_id`), so a reverse-lexicographic sort on filename is also
    reverse-chronological. No project selected is an empty history, not an error -- the
    zero-write GET sweep (`test_webapi_action_safety_contract.py`) exercises every read
    route with no project selected and expects a clean 200/404/422, never a 500.
    """
    if project is None:
        return []
    runs_dir = project / ledger.RUNS_RELDIR
    if not runs_dir.is_dir():
        return []
    entries: list[dict] = []
    for path in sorted(runs_dir.glob("*.json"), reverse=True):
        run_id = path.stem
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            entries.append({"run_id": run_id, "readable": False, "error": str(exc)})
            continue
        if not isinstance(payload, dict):
            entries.append(
                {"run_id": run_id, "readable": False, "error": "run record is not a JSON object"}
            )
            continue
        payload = dict(payload)
        payload.setdefault("run_id", run_id)
        entries.append(payload)
    return entries


def get_run(project: Path | None, run_id: str) -> dict:
    """One run: request, template, outcome, per-stage costs, retry budget.

    Every pipeline stage appears, including ones that did not run, with explicit zeros
    (FR-018). `priced` and cache figures are passed through exactly as the record carries
    them -- absent when the record never reported them, never fabricated (FR-008,
    data-model A2): a stage present in the record is returned unmodified; a stage the
    record never mentions gets the explicit-zero shape above, which itself carries no
    `priced`/`cached_input_tokens` key, reading back as unknown/absent rather than false.
    """
    if project is None:
        raise ApiError(404, "run_not_found", "select a project before reading a run record")
    path = project / ledger.RUNS_RELDIR / f"{run_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ApiError(404, "run_not_found", f"no readable run record for {run_id!r}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ApiError(404, "run_not_found", f"run record for {run_id!r} is not a JSON object")

    raw_stages = payload.get("stage_costs")
    raw_stages = raw_stages if isinstance(raw_stages, dict) else {}
    stage_costs = {
        stage: raw_stages[stage] if stage in raw_stages else dict(_ZERO_STAGE_COST)
        for stage in _CANONICAL_STAGES
    }

    result = dict(payload)
    result["run_id"] = payload.get("run_id", run_id)
    result["stage_costs"] = stage_costs
    return result


def get_pending_intent(project: Path | None) -> dict | None:
    """The pending intent awaiting a decision at the approval gate, or None.

    `stale` is computed at read time against `cabal.dotnetgen.intent.solution_fingerprint`,
    never cached (research.md R3): a pending intent is a plain file with no TTL, so its
    staleness is a live property of the current solution tree, not something that could
    go out of date sitting in memory between reads.
    """
    if project is None:
        return None
    try:
        pending = dotnetgen_intent.load_pending(project)
    except dotnetgen_intent.NoPendingIntentError:
        return None
    payload = pending.to_dict()
    # Renamed at the API boundary, deliberately. The subsystem calls this `token` (its CLI flag
    # is --intent-token), but `cabal.redaction` blanks the value of any string key containing
    # "token", which would hand the UI "[redacted]" and make the gate unusable. The identifier is
    # not a credential: it is derived from the intent plus the solution fingerprint, authorises
    # nothing on its own (redeem re-validates against the live tree), and already sits in
    # plaintext in the pending-intent file. Renaming here beats carving an exemption into shared
    # security infrastructure. `dotnetgen` keeps its own name (FR-007).
    payload["intent_ref"] = payload.pop("token")
    current_fingerprint = dotnetgen_intent.solution_fingerprint(project)
    payload["stale"] = current_fingerprint != pending.fingerprint
    return payload


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
