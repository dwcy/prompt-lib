# -*- coding: utf-8 -*-
"""Codegen action descriptors: plan, approve, reject, new_service (data-model B4).

Every mutation goes through the existing prepare/execute ticket protocol; this module
introduces no second approval mechanism. `codegen.approve`'s (and `codegen.reject`'s)
`compute_digest` binds to the pending intent's own token, not a hash of params, so the
webapi ticket can never disagree with itself between prepare and execute over something
`cabal.dotnetgen.intent` is already the sole authority on -- staleness is instead
detected explicitly, inside `execute()`, by calling the subsystem's own `redeem()` and
translating its `StaleIntentError` into `409 intent_stale` (research.md R3): binding the
digest to a *project* fingerprint instead would have let the generic ticket-precondition
check race the subsystem's own gate and raise the wrong, generic `state_changed` error.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from cabal.dotnetgen import intent as dotnetgen_intent
from cabal.dotnetgen import ledger
from cabal.dotnetgen import state as dotnetgen_state
from cabal.dotnetgen import scaffold
from cabal.dotnetgen.templates import registry as template_registry
from cabal.webapi import run_supervisor
from cabal.webapi.actions import ActionDescriptor, ActionOutcome, effect_preview
from cabal.webapi.envelope import ApiError

CODEGEN_PLAN_ACTION_ID = "codegen.plan"
CODEGEN_APPROVE_ACTION_ID = "codegen.approve"
CODEGEN_REJECT_ACTION_ID = "codegen.reject"
CODEGEN_NEW_SERVICE_ACTION_ID = "codegen.new_service"

_PLAN_SCHEMA = {
    "type": "object",
    "properties": {"request": {"type": "string"}, "template": {"type": "string"}},
    "required": ["request"],
    "additionalProperties": False,
}
_TOKEN_SCHEMA = {
    "type": "object",
    "properties": {"intent_ref": {"type": "string"}},
    "required": ["intent_ref"],
    "additionalProperties": False,
}
_NEW_SERVICE_SCHEMA = {
    "type": "object",
    "properties": {
        "template": {"type": "string"},
        "destination": {"type": "string"},
        "description": {"type": "string"},
    },
    "required": ["template", "destination", "description"],
    "additionalProperties": False,
}


def _require_project(state: Any) -> Path:
    project = getattr(state, "project", None)
    if project is None:
        raise ApiError(400, "no_project_selected", "select a project before using codegen actions")
    return Path(project)


def _load_pending_for_token(project: Path, token: str) -> dotnetgen_intent.PendingIntent:
    """Shared prepare-time lookup for approve/reject: find the pending intent and refuse
    a token that does not match it -- the same `intent_stale` vocabulary `execute()` uses
    for the deeper, fingerprint-based staleness check `redeem()` performs."""
    try:
        pending = dotnetgen_intent.load_pending(project)
    except dotnetgen_intent.NoPendingIntentError as exc:
        raise ApiError(404, "intent_not_found", str(exc)) from exc
    if pending.token != token:
        raise ApiError(409, "intent_stale", "token does not match the pending intent")
    return pending


def _intent_digest(params: dict, _state: Any) -> str:
    """`codegen.approve`/`codegen.reject` digests bind to the pending intent's own token
    (data-model B4), not to project state -- see module docstring for why."""
    return f"intent:{params['intent_ref']}"


# --- codegen.plan -------------------------------------------------------------------


def _plan_prepare(params: dict, state: Any) -> dict:
    """Writes nothing to the target project (FR-014, SC-003): only builds a preview of
    the detached command `execute()` will spawn."""
    project = _require_project(state)
    request = params["request"]
    return effect_preview(
        f"Plan a change: {request}",
        commands=[
            f"{sys.executable} -m cabal.dotnetgen plan --request {request!r} "
            f"--project {project} --json"
        ],
        scopes=["codegen"],
    )


def _plan_digest(params: dict, state: Any) -> str | None:
    """Bound to the project's own solution fingerprint (data-model B4) -- a plan
    prepared against one solution state must not silently execute against another."""
    project = getattr(state, "project", None)
    if project is None:
        return None
    return f"fingerprint:{dotnetgen_intent.solution_fingerprint(Path(project))}"


def _plan_execute(params: dict, state: Any) -> ActionOutcome:
    """Spawns a detached `cabal.dotnetgen plan` process and returns immediately
    (research.md R1); the architect stage's own proposal is what reaches the gate, so
    nothing here writes to the target project ahead of it."""
    project = _require_project(state)
    request = params["request"]
    command = [
        sys.executable, "-m", "cabal.dotnetgen", "plan",
        "--request", request, "--project", str(project), "--json",
    ]
    run_id = ledger.new_run_id()

    def runner(handle: Any) -> None:
        returncode = run_supervisor.supervise_command(
            "codegen.run",
            command=command,
            cwd=project,
            handle=handle,
            run_id=run_id,
            artifact_root=str(project),
            exclusive_resource="codegen",
            storage=state.storage,
        )
        if returncode == -1:
            handle.finish("cancelled")
        elif returncode == 0:
            handle.finish("succeeded")
        else:
            handle.finish("failed", exit_detail=f"`cabal.dotnetgen plan` exited {returncode}")

    job = state.jobs.create(CODEGEN_PLAN_ACTION_ID, runner=runner, exclusive_resource="codegen")
    return ActionOutcome(job_id=job.job_id)


# --- codegen.approve -----------------------------------------------------------------


def _approve_prepare(params: dict, state: Any) -> dict:
    """`effect_preview.files_changed` mirrors the intent's own plan, so the confirmation
    the user sees is the plan itself, not a second, independently-built preview."""
    project = _require_project(state)
    pending = _load_pending_for_token(project, params["intent_ref"])
    return effect_preview(
        f"Approve and apply: {pending.intent.summary}",
        commands=[
            f"{sys.executable} -m cabal.dotnetgen apply --intent-token {pending.token} "
            f"--project {project} --json"
        ],
        files_changed=list(pending.intent.target_files),
        scopes=["codegen"],
        backup=(
            "A failed apply leaves the pending intent intact, so approving again retries "
            "the same plan without a new proposal"
        ),
        removals=["the pending approval gate"],
    )


def _approve_execute(params: dict, state: Any) -> ActionOutcome:
    """Redeems the pending intent (refusing a stale fingerprint or a mismatched token
    with the specific `intent_stale`/`intent_not_found` codes the contract names, never
    the generic ticket-precondition path) then spawns `apply` detached. A failed apply
    must leave the pending intent intact -- `cabal.dotnetgen.intent` already only clears
    on a *successful* apply, so nothing here must (or does) clear it on failure."""
    project = _require_project(state)
    token = params["intent_ref"]
    try:
        dotnetgen_intent.redeem(project, token)
    except dotnetgen_intent.NoPendingIntentError as exc:
        raise ApiError(404, "intent_not_found", str(exc)) from exc
    except dotnetgen_intent.StaleIntentError as exc:
        raise ApiError(409, "intent_stale", str(exc)) from exc

    command = [
        sys.executable, "-m", "cabal.dotnetgen", "apply",
        "--intent-token", token, "--project", str(project), "--json",
    ]
    run_id = ledger.new_run_id()

    def runner(handle: Any) -> None:
        returncode = run_supervisor.supervise_command(
            "codegen.run",
            command=command,
            cwd=project,
            handle=handle,
            run_id=run_id,
            artifact_root=str(project / ledger.RUNS_RELDIR),
            exclusive_resource="codegen",
            storage=state.storage,
        )
        if returncode == -1:
            handle.finish("cancelled")
        elif returncode == 0:
            handle.finish("succeeded")
        else:
            handle.finish("failed", exit_detail=f"`cabal.dotnetgen apply` exited {returncode}")

    job = state.jobs.create(CODEGEN_APPROVE_ACTION_ID, runner=runner, exclusive_resource="codegen")
    return ActionOutcome(job_id=job.job_id)


# --- codegen.reject -------------------------------------------------------------------


def _reject_prepare(params: dict, state: Any) -> dict:
    project = _require_project(state)
    pending = _load_pending_for_token(project, params["intent_ref"])
    return effect_preview(
        f"Reject the proposed plan: {pending.intent.summary}",
        scopes=["codegen"],
    )


def _reject_execute(params: dict, state: Any) -> ActionOutcome:
    """Clears the pending intent, records outcome `rejected_at_gate` as a real run
    record (data-model A3), and leaves the working tree otherwise untouched -- a
    rejection is a decision worth keeping (FR-006), and the framework's own audit
    recording (triggered by returning `ActionOutcome(data=...)`) covers the ticket-level
    audit entry without this module writing one itself."""
    project = _require_project(state)
    pending = _load_pending_for_token(project, params["intent_ref"])
    dotnetgen_intent.clear(project)
    record = ledger.RunRecord(
        run_id=ledger.new_run_id(),
        project_path=str(project),
        outcome="rejected_at_gate",
    )
    ledger.write(project, record)
    return ActionOutcome(data={"outcome": "rejected_at_gate", "summary": pending.intent.summary})


# --- codegen.new_service ---------------------------------------------------------------


def _resolve_destination(project: Path, destination: str) -> Path:
    """Resolves `destination` relative to the selected project and refuses any path that
    escapes it *after* normalisation (research.md R10, FR-011a) -- a relative path
    containing `..` would otherwise pass a naive prefix test on the raw string."""
    project_resolved = project.resolve()
    candidate = (project_resolved / destination).resolve()
    try:
        candidate.relative_to(project_resolved)
    except ValueError:
        raise ApiError(
            400,
            "destination_outside_project",
            f"destination {destination!r} resolves outside the selected project",
        ) from None
    return candidate


def _destination_conflicts(destination: Path) -> bool:
    if destination.is_dir():
        return any(destination.iterdir())
    return destination.exists()


def _new_service_prepare(params: dict, state: Any) -> dict:
    """The preview shows the resolved absolute destination path, so the user confirms
    where the tree actually lands (research.md R10)."""
    project = _require_project(state)
    destination = _resolve_destination(project, params["destination"])
    if _destination_conflicts(destination):
        raise ApiError(
            409, "destination_not_empty", f"{destination} already exists and is not empty"
        )
    template = params["template"]
    return effect_preview(
        f"Scaffold a new {template!r} service at {destination}",
        commands=[f"cabal.dotnetgen new --template {template} --out {destination}"],
        files_changed=[str(destination)],
        scopes=["codegen"],
        # A create-only action has nothing pre-existing to remove; "removals" and
        # "backup" instead describe how to undo it, which `_validate_preview` requires
        # non-empty/non-null for every destructive descriptor regardless of direction.
        backup=f"Nothing existed at {destination} before scaffolding; delete it to undo",
        removals=[str(destination)],
    )


def _new_service_execute(params: dict, state: Any) -> ActionOutcome:
    """Post-normalisation escape refusal and non-empty-destination refusal are enforced
    again here (not just at prepare), since the ticket's generic precondition digest
    (a hash of params) does not itself encode "does this destination still not exist" --
    a directory could appear between prepare and execute."""
    project = _require_project(state)
    destination = _resolve_destination(project, params["destination"])
    if _destination_conflicts(destination):
        raise ApiError(
            409, "destination_not_empty", f"{destination} already exists and is not empty"
        )
    try:
        scaffold_plan = scaffold.plan(destination, params["template"])
    except template_registry.TemplateError as exc:
        raise ApiError(422, "params_invalid", str(exc)) from exc
    try:
        result = scaffold.execute(scaffold_plan)
    except (scaffold.ScaffoldError, dotnetgen_state.StateError) as exc:
        raise ApiError(500, "scaffold_failed", str(exc)) from exc
    return ActionOutcome(data=result.describe())


CODEGEN_PLAN_DESCRIPTOR = ActionDescriptor(
    action_id=CODEGEN_PLAN_ACTION_ID,
    module="codegen",
    destructive=False,
    params_schema=_PLAN_SCHEMA,
    prepare=_plan_prepare,
    execute=_plan_execute,
    compute_digest=_plan_digest,
)

CODEGEN_APPROVE_DESCRIPTOR = ActionDescriptor(
    action_id=CODEGEN_APPROVE_ACTION_ID,
    module="codegen",
    destructive=True,
    params_schema=_TOKEN_SCHEMA,
    prepare=_approve_prepare,
    execute=_approve_execute,
    compute_digest=_intent_digest,
)

CODEGEN_REJECT_DESCRIPTOR = ActionDescriptor(
    action_id=CODEGEN_REJECT_ACTION_ID,
    module="codegen",
    destructive=False,
    params_schema=_TOKEN_SCHEMA,
    prepare=_reject_prepare,
    execute=_reject_execute,
    compute_digest=_intent_digest,
)

CODEGEN_NEW_SERVICE_DESCRIPTOR = ActionDescriptor(
    action_id=CODEGEN_NEW_SERVICE_ACTION_ID,
    module="codegen",
    destructive=True,
    params_schema=_NEW_SERVICE_SCHEMA,
    prepare=_new_service_prepare,
    execute=_new_service_execute,
)

CODEGEN_DESCRIPTORS = (
    CODEGEN_PLAN_DESCRIPTOR,
    CODEGEN_APPROVE_DESCRIPTOR,
    CODEGEN_REJECT_DESCRIPTOR,
    CODEGEN_NEW_SERVICE_DESCRIPTOR,
)
