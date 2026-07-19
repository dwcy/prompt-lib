# -*- coding: utf-8 -*-
"""Codex Parity action descriptors: deploy Codex assets and apply project-local Codex scaffold."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cabal.codex_setup.diff_apply import apply_codex_statuses, ensure_codex_target
from cabal.codex_setup.local_setup import apply_codex_local_group, build_codex_local_plan
from cabal.codex_setup.paths import CODEX_SOURCE_DIR
from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.config_service import deploy_digest, resolve_statuses
from cabal.webapi.envelope import ApiError, compute_precondition_digest
from cabal.webapi.local_config_service import strip_rich_markup

CODEX_APPLY_ACTION_ID = "codex.apply"
CODEX_LOCAL_APPLY_ACTION_ID = "codex.local_apply"

_APPLY_SCHEMA = {
    "type": "object",
    "properties": {"paths": {"type": "array", "items": {"type": "string"}}},
    "required": ["paths"],
    "additionalProperties": False,
}

_LOCAL_APPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "item_keys": {"type": "array", "items": {"type": "string"}},
        "template": {"type": ["string", "null"]},
    },
    "required": ["action", "item_keys"],
    "additionalProperties": False,
}

_CODEX_TEMPLATE_DIR = CODEX_SOURCE_DIR / "project-templates"
_ALL_CODEX_LOCAL_ACTIONS = {"scaffold": True, "template": True, "skills": True}


def _require_project(state: Any) -> Path:
    project = getattr(state, "project", None)
    if project is None:
        raise ApiError(422, "params_invalid", "Select a project before changing Codex local config")
    return Path(project)


def _resolve_template(template_stem: str | None) -> Path | None:
    if not template_stem:
        return None
    candidate = _CODEX_TEMPLATE_DIR / f"{template_stem}.md"
    return candidate if candidate.exists() else None


def _codex_plan(project: Path, template_stem: str | None) -> list[dict[str, Any]]:
    return build_codex_local_plan(project, _ALL_CODEX_LOCAL_ACTIONS, _resolve_template(template_stem))


def _selected_children(state: Any, params: dict) -> list[dict[str, Any]]:
    project = _require_project(state)
    groups = _codex_plan(project, params.get("template"))
    group = next((g for g in groups if g["action"] == params["action"]), None)
    if group is None:
        raise ApiError(422, "params_invalid", f"Unknown Codex local action {params['action']!r}")
    wanted = set(params["item_keys"])
    return [child for child in group["children"] if child["key"] in wanted and child.get("op") is not None]


def _apply_prepare(params: dict, _state: Any) -> dict:
    paths = list(params["paths"])
    resolve_statuses("codex", paths)
    return {
        "summary": f"Deploy {len(paths)} file(s) to the Codex target",
        "commands": [],
        "files_changed": paths,
        "scopes": ["codex"],
        "backup": None,
        "removals": [],
    }


def _apply_execute(params: dict, state: Any) -> ActionOutcome:
    paths = list(params["paths"])

    def runner(handle) -> None:
        ensure_codex_target()
        resolved = resolve_statuses("codex", paths)
        for status, path in resolved:
            apply_codex_statuses([status])
            handle.emit_line(f"Deployed {path} ({status.state.lower()})")
        handle.finish("succeeded")

    job = state.jobs.create(CODEX_APPLY_ACTION_ID, runner=runner, exclusive_resource="codex-apply")
    return ActionOutcome(job_id=job.job_id)


def _local_apply_prepare(params: dict, state: Any) -> dict:
    chosen = _selected_children(state, params)
    labels = [child["label"] for child in chosen]
    return {
        "summary": f"Apply Codex local config '{params['action']}' ({len(chosen)} item(s))",
        "commands": [],
        "files_changed": labels,
        "scopes": ["codex"],
        "backup": None,
        "removals": [],
    }


def _local_apply_digest(params: dict, state: Any) -> str:
    project = getattr(state, "project", None)
    if project is None:
        return compute_precondition_digest({"action": params.get("action"), "project": None})
    groups = _codex_plan(Path(project), params.get("template"))
    group = next((g for g in groups if g["action"] == params.get("action")), None)
    states = [(child["key"], child.get("state")) for child in group["children"]] if group else []
    return compute_precondition_digest({"action": params.get("action"), "states": states})


def _local_apply_execute(params: dict, state: Any) -> ActionOutcome:
    chosen = _selected_children(state, params)
    action = params["action"]

    def runner(handle) -> None:
        lines = apply_codex_local_group(action, chosen)
        for line in lines:
            for stripped in strip_rich_markup(line).splitlines():
                if stripped.strip():
                    handle.emit_line(stripped)
        handle.finish("succeeded")

    job = state.jobs.create(
        CODEX_LOCAL_APPLY_ACTION_ID, runner=runner, exclusive_resource=f"codex-local:{action}"
    )
    return ActionOutcome(job_id=job.job_id)


CODEX_APPLY_DESCRIPTOR = ActionDescriptor(
    action_id=CODEX_APPLY_ACTION_ID,
    module="codex",
    destructive=False,
    backup_policy=None,
    params_schema=_APPLY_SCHEMA,
    prepare=_apply_prepare,
    execute=_apply_execute,
    compute_digest=lambda _params, _state: deploy_digest("codex"),
)

CODEX_LOCAL_APPLY_DESCRIPTOR = ActionDescriptor(
    action_id=CODEX_LOCAL_APPLY_ACTION_ID,
    module="codex",
    destructive=False,
    backup_policy=None,
    params_schema=_LOCAL_APPLY_SCHEMA,
    prepare=_local_apply_prepare,
    execute=_local_apply_execute,
    compute_digest=_local_apply_digest,
)

CODEX_DESCRIPTORS = (CODEX_APPLY_DESCRIPTOR, CODEX_LOCAL_APPLY_DESCRIPTOR)
