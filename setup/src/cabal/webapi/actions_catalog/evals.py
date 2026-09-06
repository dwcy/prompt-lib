# -*- coding: utf-8 -*-
"""Eval-harness action descriptors: launch, cancel, resume, definition save/delete, and
worktree cleanup (data-model B4).

Every run-starting action takes `exclusive_resource: "evals"`, kept separate from
`"codegen"` so the two modules run independently (research.md R7). Definition mutations
are gated on validation and a content-hash precondition
(`contracts/definition-roundtrip.md`). Bodies raise `NotWiredError` until their owning
task lands -- see `contracts/evals-api.md`.
"""

from __future__ import annotations

from typing import Any

from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.run_supervisor import NotWiredError

EVALS_LAUNCH_ACTION_ID = "evals.launch"
EVALS_CANCEL_ACTION_ID = "evals.cancel"
EVALS_RESUME_ACTION_ID = "evals.resume"
EVALS_DEFINITION_SAVE_ACTION_ID = "evals.definition_save"
EVALS_DEFINITION_DELETE_ACTION_ID = "evals.definition_delete"
EVALS_WORKTREE_CLEANUP_ACTION_ID = "evals.worktree_cleanup"

_LAUNCH_SCHEMA = {
    "type": "object",
    "properties": {
        "baseline": {"type": "string"},
        "candidate": {"type": "string"},
        "tasks": {"type": "array", "items": {"type": "string"}},
        "runs": {"type": "integer"},
        "adapter": {"type": "string"},
    },
    "required": ["baseline", "candidate", "tasks", "runs"],
    "additionalProperties": False,
}
_RUN_ID_SCHEMA = {
    "type": "object",
    "properties": {"run_id": {"type": "string"}},
    "required": ["run_id"],
    "additionalProperties": False,
}
_DEFINITION_SAVE_SCHEMA = {
    "type": "object",
    "properties": {"path": {"type": "string"}, "content": {"type": "object"}},
    "required": ["path", "content"],
    "additionalProperties": False,
}
_PATH_SCHEMA = {
    "type": "object",
    "properties": {"path": {"type": "string"}},
    "required": ["path"],
    "additionalProperties": False,
}


def _launch_prepare(params: dict, state: Any) -> dict:
    """Implemented in T042: refused with `409 definitions_invalid` on a failed tree."""
    raise NotWiredError("evals.launch.prepare", "T042")


def _launch_execute(params: dict, state: Any) -> ActionOutcome:
    """Implemented in T042: spawns detached, reports the isolated config directory used
    (FR-034, SC-011)."""
    raise NotWiredError("evals.launch.execute", "T042")


def _cancel_prepare(params: dict, state: Any) -> dict:
    """Implemented in T043."""
    raise NotWiredError("evals.cancel.prepare", "T043")


def _cancel_execute(params: dict, state: Any) -> ActionOutcome:
    """Implemented in T043: terminates the process tree, idempotent on a finished run."""
    raise NotWiredError("evals.cancel.execute", "T043")


def _resume_prepare(params: dict, state: Any) -> dict:
    """Implemented in T076."""
    raise NotWiredError("evals.resume.prepare", "T076")


def _resume_execute(params: dict, state: Any) -> ActionOutcome:
    """Implemented in T076: completion determined from the manifest and cell
    directories, never a job record (FR-036, SC-008)."""
    raise NotWiredError("evals.resume.execute", "T076")


def _definition_save_prepare(params: dict, state: Any) -> dict:
    """Implemented in T065: validated before writing; nothing written on refusal."""
    raise NotWiredError("evals.definition_save.prepare", "T065")


def _definition_save_execute(params: dict, state: Any) -> ActionOutcome:
    """Implemented in T065: atomic write per `contracts/definition-roundtrip.md`."""
    raise NotWiredError("evals.definition_save.execute", "T065")


def _definition_save_digest(params: dict, state: Any) -> str | None:
    """Implemented in T065: bound to the file's current content hash (FR-053)."""
    raise NotWiredError("evals.definition_save.compute_digest", "T065")


def _definition_delete_prepare(params: dict, state: Any) -> dict:
    """Implemented in T066: preview names the stored runs this decouples (FR-054)."""
    raise NotWiredError("evals.definition_delete.prepare", "T066")


def _definition_delete_execute(params: dict, state: Any) -> ActionOutcome:
    """Implemented in T066."""
    raise NotWiredError("evals.definition_delete.execute", "T066")


def _worktree_cleanup_prepare(params: dict, state: Any) -> dict:
    """Implemented in T077."""
    raise NotWiredError("evals.worktree_cleanup.prepare", "T077")


def _worktree_cleanup_execute(params: dict, state: Any) -> ActionOutcome:
    """Implemented in T077: refuses to remove a worktree belonging to a live run."""
    raise NotWiredError("evals.worktree_cleanup.execute", "T077")


EVALS_LAUNCH_DESCRIPTOR = ActionDescriptor(
    action_id=EVALS_LAUNCH_ACTION_ID,
    module="evals",
    destructive=False,
    params_schema=_LAUNCH_SCHEMA,
    prepare=_launch_prepare,
    execute=_launch_execute,
)

EVALS_CANCEL_DESCRIPTOR = ActionDescriptor(
    action_id=EVALS_CANCEL_ACTION_ID,
    module="evals",
    destructive=True,
    params_schema=_RUN_ID_SCHEMA,
    prepare=_cancel_prepare,
    execute=_cancel_execute,
)

EVALS_RESUME_DESCRIPTOR = ActionDescriptor(
    action_id=EVALS_RESUME_ACTION_ID,
    module="evals",
    destructive=False,
    params_schema=_RUN_ID_SCHEMA,
    prepare=_resume_prepare,
    execute=_resume_execute,
)

EVALS_DEFINITION_SAVE_DESCRIPTOR = ActionDescriptor(
    action_id=EVALS_DEFINITION_SAVE_ACTION_ID,
    module="evals",
    destructive=True,
    params_schema=_DEFINITION_SAVE_SCHEMA,
    prepare=_definition_save_prepare,
    execute=_definition_save_execute,
    compute_digest=_definition_save_digest,
)

EVALS_DEFINITION_DELETE_DESCRIPTOR = ActionDescriptor(
    action_id=EVALS_DEFINITION_DELETE_ACTION_ID,
    module="evals",
    destructive=True,
    params_schema=_PATH_SCHEMA,
    prepare=_definition_delete_prepare,
    execute=_definition_delete_execute,
)

EVALS_WORKTREE_CLEANUP_DESCRIPTOR = ActionDescriptor(
    action_id=EVALS_WORKTREE_CLEANUP_ACTION_ID,
    module="evals",
    destructive=True,
    params_schema=_PATH_SCHEMA,
    prepare=_worktree_cleanup_prepare,
    execute=_worktree_cleanup_execute,
)

EVALS_DESCRIPTORS = (
    EVALS_LAUNCH_DESCRIPTOR,
    EVALS_CANCEL_DESCRIPTOR,
    EVALS_RESUME_DESCRIPTOR,
    EVALS_DEFINITION_SAVE_DESCRIPTOR,
    EVALS_DEFINITION_DELETE_DESCRIPTOR,
    EVALS_WORKTREE_CLEANUP_DESCRIPTOR,
)
