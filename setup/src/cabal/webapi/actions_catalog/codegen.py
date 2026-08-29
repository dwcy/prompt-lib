# -*- coding: utf-8 -*-
"""Codegen action descriptors: plan, approve, reject, new_service (data-model B4).

Every mutation goes through the existing prepare/execute ticket protocol; this module
introduces no second approval mechanism. `codegen.approve`'s `compute_digest` binds to
the pending intent's own token, not a hash of params, so the webapi ticket and the
subsystem's on-disk gate cannot disagree by construction (research.md R3). Bodies raise
`NotWiredError` until their owning task lands -- see `contracts/codegen-api.md`.
"""

from __future__ import annotations

from typing import Any

from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.run_supervisor import NotWiredError

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
    "properties": {"token": {"type": "string"}},
    "required": ["token"],
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


def _plan_prepare(params: dict, state: Any) -> dict:
    """Implemented in T018: must write nothing to the target project (FR-014, SC-003)."""
    raise NotWiredError("codegen.plan.prepare", "T018")


def _plan_execute(params: dict, state: Any) -> ActionOutcome:
    """Implemented in T018: spawns detached and returns immediately (research.md R1)."""
    raise NotWiredError("codegen.plan.execute", "T018")


def _approve_prepare(params: dict, state: Any) -> dict:
    """Implemented in T019: `effect_preview.files_changed` mirrors the intent's own plan."""
    raise NotWiredError("codegen.approve.prepare", "T019")


def _approve_execute(params: dict, state: Any) -> ActionOutcome:
    """Implemented in T019: a failed apply must leave the pending intent intact."""
    raise NotWiredError("codegen.approve.execute", "T019")


def _approve_digest(params: dict, state: Any) -> str | None:
    """Implemented in T019: bound to the pending intent's token, per research.md R3."""
    raise NotWiredError("codegen.approve.compute_digest", "T019")


def _reject_prepare(params: dict, state: Any) -> dict:
    """Implemented in T020."""
    raise NotWiredError("codegen.reject.prepare", "T020")


def _reject_execute(params: dict, state: Any) -> ActionOutcome:
    """Implemented in T020: clears the intent and audits outcome `rejected at gate`."""
    raise NotWiredError("codegen.reject.execute", "T020")


def _new_service_prepare(params: dict, state: Any) -> dict:
    """Implemented in T021: preview shows the resolved absolute destination path."""
    raise NotWiredError("codegen.new_service.prepare", "T021")


def _new_service_execute(params: dict, state: Any) -> ActionOutcome:
    """Implemented in T021: post-normalisation escape and non-empty-destination refusal
    (research.md R10)."""
    raise NotWiredError("codegen.new_service.execute", "T021")


CODEGEN_PLAN_DESCRIPTOR = ActionDescriptor(
    action_id=CODEGEN_PLAN_ACTION_ID,
    module="codegen",
    destructive=False,
    params_schema=_PLAN_SCHEMA,
    prepare=_plan_prepare,
    execute=_plan_execute,
)

CODEGEN_APPROVE_DESCRIPTOR = ActionDescriptor(
    action_id=CODEGEN_APPROVE_ACTION_ID,
    module="codegen",
    destructive=True,
    params_schema=_TOKEN_SCHEMA,
    prepare=_approve_prepare,
    execute=_approve_execute,
    compute_digest=_approve_digest,
)

CODEGEN_REJECT_DESCRIPTOR = ActionDescriptor(
    action_id=CODEGEN_REJECT_ACTION_ID,
    module="codegen",
    destructive=False,
    params_schema=_TOKEN_SCHEMA,
    prepare=_reject_prepare,
    execute=_reject_execute,
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
