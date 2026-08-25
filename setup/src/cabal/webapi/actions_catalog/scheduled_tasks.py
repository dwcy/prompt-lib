"""Confirmation-guarded scheduled-task deletion."""

from __future__ import annotations

from typing import Any

from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.scheduled_tasks_service import (
    delete_scheduled_task,
    find_scheduled_task,
    scheduled_task_digest,
)

SCHEDULED_TASKS_DELETE_ACTION_ID = "scheduled_tasks.delete"

_DELETE_SCHEMA = {
    "type": "object",
    "properties": {
        "provider": {"type": "string", "enum": ["claude", "codex"]},
        "task_id": {"type": "string", "minLength": 1},
    },
    "required": ["provider", "task_id"],
    "additionalProperties": False,
}


def _delete_prepare(params: dict, _state: Any) -> dict:
    task = find_scheduled_task(params["provider"], params["task_id"])
    source_label = "Claude Desktop" if task.provider == "claude" else "Codex"
    return {
        "summary": f"Delete {source_label} scheduled task '{task.name}'",
        "commands": [],
        "files_changed": [str(path) for path in task.source_paths],
        "scopes": ["scheduled_tasks", task.provider],
        "backup": "No backup; the task definition and its local automation memory are removed",
        "removals": [f"{source_label}: {task.name} ({task.provider_task_id})"],
    }


def _delete_execute(params: dict, _state: Any) -> ActionOutcome:
    return ActionOutcome(data=delete_scheduled_task(params["provider"], params["task_id"]))


SCHEDULED_TASKS_DELETE_DESCRIPTOR = ActionDescriptor(
    action_id=SCHEDULED_TASKS_DELETE_ACTION_ID,
    module="scheduled_tasks",
    destructive=True,
    backup_policy=None,
    params_schema=_DELETE_SCHEMA,
    prepare=_delete_prepare,
    execute=_delete_execute,
    compute_digest=lambda params, _state: scheduled_task_digest(params["provider"], params["task_id"]),
)
