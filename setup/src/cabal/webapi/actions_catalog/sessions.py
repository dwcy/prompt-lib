# -*- coding: utf-8 -*-
"""US4 action descriptors: sessions.delete and models.assign."""

from __future__ import annotations

from typing import Any

from cabal import model_assignments
from cabal.webapi.account_service import models_digest
from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.envelope import ApiError
from cabal.webapi.sessions_service import delete_session_payload, find_session_file, session_digest

SESSIONS_DELETE_ACTION_ID = "sessions.delete"
MODELS_ASSIGN_ACTION_ID = "models.assign"

_SESSION_DELETE_SCHEMA = {
    "type": "object",
    "properties": {"session_id": {"type": "string"}},
    "required": ["session_id"],
    "additionalProperties": False,
}

_MODEL_ASSIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "asset_kind": {"type": "string", "enum": ["agent", "skill"]},
        "asset_name": {"type": "string"},
        "model": {"type": "string"},
    },
    "required": ["asset_kind", "asset_name", "model"],
    "additionalProperties": False,
}


def _delete_prepare(params: dict, _state: Any) -> dict:
    session = find_session_file(params["session_id"])
    return {
        "summary": f"Delete session transcript {params['session_id']}",
        "commands": [],
        "files_changed": [],
        "scopes": ["sessions"],
        "backup": "No backup; transcript deletion is permanent",
        "removals": [str(session.log_path)],
    }


def _delete_execute(params: dict, _state: Any) -> ActionOutcome:
    return ActionOutcome(data=delete_session_payload(params["session_id"]))


def _assign_prepare(params: dict, _state: Any) -> dict:
    model = params["model"]
    if model not in model_assignments.VALID_MODEL_ALIASES and model not in model_assignments.KNOWN_MODEL_IDS:
        raise ApiError(422, "params_invalid", f"Unknown model value {model!r}")
    return {
        "summary": f"Assign {params['asset_kind']} {params['asset_name']} to {model}",
        "commands": [],
        "files_changed": [f"{params['asset_kind']}:{params['asset_name']}"],
        "scopes": ["model_assignments"],
        "backup": None,
        "removals": [],
    }


def _assign_execute(params: dict, _state: Any) -> ActionOutcome:
    written = model_assignments.set_model(
        params["asset_kind"],
        params["asset_name"],
        params["model"],
    )
    return ActionOutcome(data={"written": [str(path) for path in written]})


SESSIONS_DELETE_DESCRIPTOR = ActionDescriptor(
    action_id=SESSIONS_DELETE_ACTION_ID,
    module="sessions",
    destructive=True,
    backup_policy=None,
    params_schema=_SESSION_DELETE_SCHEMA,
    prepare=_delete_prepare,
    execute=_delete_execute,
    compute_digest=lambda params, _state: session_digest(params["session_id"]),
)

MODELS_ASSIGN_DESCRIPTOR = ActionDescriptor(
    action_id=MODELS_ASSIGN_ACTION_ID,
    module="model_assignments",
    destructive=False,
    backup_policy=None,
    params_schema=_MODEL_ASSIGN_SCHEMA,
    prepare=_assign_prepare,
    execute=_assign_execute,
    compute_digest=lambda params, _state: models_digest(params["asset_kind"], params["asset_name"]),
)

OBSERVABILITY_DESCRIPTORS = (SESSIONS_DELETE_DESCRIPTOR, MODELS_ASSIGN_DESCRIPTOR)
