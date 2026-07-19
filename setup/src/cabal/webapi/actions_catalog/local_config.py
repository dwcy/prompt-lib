# -*- coding: utf-8 -*-
"""Settings + Local Project Config action descriptors: settings.toggle / settings.reset_local
(instant local-override writes) and local_config.apply_group (streamed scaffold apply, since
the git action shells out). All are project-scoped. Wraps claude_settings / local_setup."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cabal.claude_settings import CATALOG, read_local, reset_local, write_local
from cabal.local_setup import apply_group
from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.envelope import ApiError, compute_precondition_digest
from cabal.webapi.local_config_service import local_plan, strip_rich_markup

SETTINGS_TOGGLE_ACTION_ID = "settings.toggle"
SETTINGS_RESET_LOCAL_ACTION_ID = "settings.reset_local"
LOCAL_CONFIG_APPLY_GROUP_ACTION_ID = "local_config.apply_group"

_CATALOG_KEYS = {setting.key: setting for setting in CATALOG}

_TOGGLE_SCHEMA = {
    "type": "object",
    "properties": {"key": {"type": "string"}, "value": {"type": "boolean"}},
    "required": ["key", "value"],
    "additionalProperties": False,
}
_APPLY_GROUP_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "item_keys": {"type": "array", "items": {"type": "string"}},
        "template": {"type": ["string", "null"]},
        "gitignore": {"type": ["string", "null"]},
    },
    "required": ["action", "item_keys"],
    "additionalProperties": False,
}


def _require_project(state: Any) -> Path:
    project = getattr(state, "project", None)
    if project is None:
        raise ApiError(422, "params_invalid", "Select a project before changing local configuration")
    return Path(project)


# --- settings.toggle --------------------------------------------------------


def _toggle_prepare(params: dict, _state: Any) -> dict:
    setting = _CATALOG_KEYS.get(params["key"])
    if setting is None:
        raise ApiError(422, "params_invalid", f"Unknown setting {params['key']!r}")
    return {
        "summary": f"Set '{setting.label}' to {params['value']} as a local override",
        "commands": [],
        "files_changed": ["settings.local.json"],
        "scopes": ["settings"],
        "backup": None,
        "removals": [],
    }


def _toggle_digest(params: dict, state: Any) -> str:
    project = getattr(state, "project", None)
    local = read_local(Path(project)) if project is not None else {}
    return compute_precondition_digest({"key": params.get("key"), "current": local.get(params.get("key"))})


def _toggle_execute(params: dict, state: Any) -> ActionOutcome:
    project = _require_project(state)
    if params["key"] not in _CATALOG_KEYS:
        raise ApiError(422, "params_invalid", f"Unknown setting {params['key']!r}")
    path = write_local(project, params["key"], params["value"])
    return ActionOutcome(data={"key": params["key"], "value": params["value"], "target_file": str(path)})


# --- settings.reset_local ---------------------------------------------------


def _reset_prepare(_params: dict, state: Any) -> dict:
    project = getattr(state, "project", None)
    overridden = [key for key in _CATALOG_KEYS if project is not None and key in read_local(Path(project))]
    if not overridden:
        return {
            "summary": "No local setting overrides to reset",
            "commands": [],
            "files_changed": [],
            "scopes": ["settings"],
            "backup": None,
            "removals": [],
        }
    return {
        "summary": f"Reset {len(overridden)} local setting override(s) to the global baseline",
        "commands": [],
        "files_changed": ["settings.local.json"],
        "scopes": ["settings"],
        "backup": None,
        "removals": overridden,
    }


def _reset_digest(_params: dict, state: Any) -> str:
    project = getattr(state, "project", None)
    local = read_local(Path(project)) if project is not None else {}
    return compute_precondition_digest({"overrides": sorted(k for k in _CATALOG_KEYS if k in local)})


def _reset_execute(_params: dict, state: Any) -> ActionOutcome:
    project = _require_project(state)
    removed = reset_local(project)
    return ActionOutcome(data={"removed": removed})


# --- local_config.apply_group -----------------------------------------------


def _selected_children(state: Any, params: dict) -> tuple[Path, list[dict[str, Any]]]:
    project = _require_project(state)
    groups = local_plan(project, template_stem=params.get("template"), gitignore_stem=params.get("gitignore"))
    group = next((g for g in groups if g["action"] == params["action"]), None)
    if group is None:
        raise ApiError(422, "params_invalid", f"Unknown local-config action {params['action']!r}")
    wanted = set(params["item_keys"])
    chosen = [child for child in group["children"] if child["key"] in wanted and child.get("op") is not None]
    return project, chosen


def _apply_group_prepare(params: dict, state: Any) -> dict:
    _project, chosen = _selected_children(state, params)
    labels = [child["label"] for child in chosen]
    return {
        "summary": f"Apply local config '{params['action']}' ({len(chosen)} item(s))",
        "commands": ["git init"] if params["action"] == "git" else [],
        "files_changed": labels,
        "scopes": ["local_config"],
        "backup": None,
        "removals": [],
    }


def _apply_group_digest(params: dict, state: Any) -> str:
    project = getattr(state, "project", None)
    if project is None:
        return compute_precondition_digest({"action": params.get("action"), "project": None})
    groups = local_plan(Path(project), template_stem=params.get("template"), gitignore_stem=params.get("gitignore"))
    group = next((g for g in groups if g["action"] == params.get("action")), None)
    states = [(c["key"], c.get("state")) for c in group["children"]] if group else []
    return compute_precondition_digest({"action": params.get("action"), "states": states})


def _apply_group_execute(params: dict, state: Any) -> ActionOutcome:
    project, chosen = _selected_children(state, params)
    action = params["action"]

    def runner(handle) -> None:
        lines = apply_group(action, chosen, project)
        for line in lines:
            for stripped in strip_rich_markup(line).splitlines():
                if stripped.strip():
                    handle.emit_line(stripped)
        handle.finish("succeeded")

    job = state.jobs.create(
        LOCAL_CONFIG_APPLY_GROUP_ACTION_ID, runner=runner, exclusive_resource=f"local_config:{action}"
    )
    return ActionOutcome(job_id=job.job_id)


SETTINGS_TOGGLE_DESCRIPTOR = ActionDescriptor(
    action_id=SETTINGS_TOGGLE_ACTION_ID,
    module="settings",
    destructive=False,
    backup_policy=None,
    params_schema=_TOGGLE_SCHEMA,
    prepare=_toggle_prepare,
    execute=_toggle_execute,
    compute_digest=_toggle_digest,
)

SETTINGS_RESET_LOCAL_DESCRIPTOR = ActionDescriptor(
    action_id=SETTINGS_RESET_LOCAL_ACTION_ID,
    module="settings",
    destructive=False,
    backup_policy=None,
    params_schema={"type": "object", "properties": {}, "additionalProperties": False},
    prepare=_reset_prepare,
    execute=_reset_execute,
    compute_digest=_reset_digest,
)

LOCAL_CONFIG_APPLY_GROUP_DESCRIPTOR = ActionDescriptor(
    action_id=LOCAL_CONFIG_APPLY_GROUP_ACTION_ID,
    module="local_config",
    destructive=False,
    backup_policy=None,
    params_schema=_APPLY_GROUP_SCHEMA,
    prepare=_apply_group_prepare,
    execute=_apply_group_execute,
    compute_digest=_apply_group_digest,
)

LOCAL_CONFIG_DESCRIPTORS = (
    SETTINGS_TOGGLE_DESCRIPTOR,
    SETTINGS_RESET_LOCAL_DESCRIPTOR,
    LOCAL_CONFIG_APPLY_GROUP_DESCRIPTOR,
)
