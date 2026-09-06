"""Cross-module job action descriptors."""

from __future__ import annotations

from typing import Any

from cabal.webapi.actions import ActionDescriptor, ActionOutcome, effect_preview
from cabal.webapi.envelope import ApiError, compute_precondition_digest

JOBS_CANCEL_ACTION_ID = "jobs.cancel"

_JOBS_CANCEL_SCHEMA = {
    "type": "object",
    "properties": {"job_id": {"type": "string"}},
    "required": ["job_id"],
    "additionalProperties": False,
}


def _job_record(job_id: str, state: Any) -> dict:
    record = state.jobs.get_record(job_id)
    if record is None:
        raise ApiError(404, "job_not_found", f"Unknown job {job_id!r}")
    return record


def _cancel_prepare(params: dict, state: Any) -> dict:
    job_id = params["job_id"]
    record = _job_record(job_id, state)
    if record["state"] not in {"queued", "running"}:
        raise ApiError(409, "job_not_cancellable", f"Job {job_id!r} is already {record['state']}")
    return effect_preview(
        f"Cancel {record['kind']} job {job_id}",
        scopes=["jobs"],
        backup="No backup; rerun the original action to recover unfinished work",
        removals=[f"remaining work for {record['kind']} job {job_id}"],
    )


def _cancel_execute(params: dict, state: Any) -> ActionOutcome:
    job_id = params["job_id"]
    record = _job_record(job_id, state)
    if record["state"] not in {"queued", "running"}:
        raise ApiError(409, "job_not_cancellable", f"Job {job_id!r} is already {record['state']}")
    if not state.jobs.cancel(job_id):
        raise ApiError(404, "job_not_found", f"Unknown job {job_id!r}")
    return ActionOutcome(data=_job_record(job_id, state))


def _cancel_digest(params: dict, state: Any) -> str:
    record = _job_record(params["job_id"], state)
    return compute_precondition_digest(
        {
            "job_id": record["job_id"],
            "kind": record["kind"],
            "cancellable": record["state"] in {"queued", "running"},
        }
    )


JOBS_CANCEL_DESCRIPTOR = ActionDescriptor(
    action_id=JOBS_CANCEL_ACTION_ID,
    module="jobs",
    destructive=True,
    params_schema=_JOBS_CANCEL_SCHEMA,
    prepare=_cancel_prepare,
    execute=_cancel_execute,
    compute_digest=_cancel_digest,
)
