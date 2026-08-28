# -*- coding: utf-8 -*-
"""tools.install / tools.update action descriptors: preview, runtime backup, Job-backed install."""

from __future__ import annotations

from typing import Any

from cabal.installers.runtime_backups import backup_before_install
from cabal.tool_catalog import ToolDefinition, clean_console_output, get_tool_definition
from cabal.tools import _installer_for, _probe_key, _tool_unavailable_reason
from cabal.webapi.actions import ActionDescriptor, ActionOutcome, effect_preview
from cabal.webapi.envelope import ApiError, compute_precondition_digest

TOOLS_INSTALL_ACTION_ID = "tools.install"
TOOLS_UPDATE_ACTION_ID = "tools.update"

_PARAMS_SCHEMA = {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "version": {"type": ["string", "null"]},
    },
    "required": ["key"],
    "additionalProperties": False,
}


def _require_installable(key: str) -> tuple[ToolDefinition, tuple[str, Any]]:
    definition = get_tool_definition(key)
    if definition is None:
        raise ApiError(422, "params_invalid", f"Unknown tool key {key!r}")
    meta = _installer_for(key)
    if meta is None:
        raise ApiError(422, "params_invalid", f"{definition.label} has no automated installer")
    reason = _tool_unavailable_reason(key)
    if reason is not None:
        raise ApiError(422, "params_invalid", reason)
    return definition, meta


def _tools_digest(params: dict, _state: Any) -> str:
    """Digest over the tool's current probed state, so a manual install mid-review invalidates."""
    key = params.get("key", "")
    try:
        current = _probe_key(key)
    except Exception:
        current = None
    return compute_precondition_digest({"key": key, "current": current})


def _prepare_for(mode: str):
    verb = "Install" if mode == "install" else "Update"

    def _prepare(params: dict, _state: Any) -> dict:
        definition, _meta = _require_installable(params["key"])
        version = params.get("version")
        summary = f"{verb} {definition.label}"
        if version:
            summary += f" ({version})"
        return effect_preview(summary, scopes=["tools"], backup=definition.backup_policy)

    return _prepare


def _execute_for(mode: str):
    def _execute(params: dict, state: Any) -> ActionOutcome:
        key = params["key"]
        definition, (label, installer) = _require_installable(key)

        def runner(handle) -> None:
            if definition.backup_policy:
                handle.emit_line(f"Capturing runtime backup for {key}...")
                backup_ok, backup_msg = backup_before_install(definition.backup_policy)
                for line in clean_console_output(backup_msg).splitlines():
                    handle.emit_line(line)
                if not backup_ok:
                    handle.finish("failed", exit_detail=backup_msg)
                    return
            handle.emit_line(f"Running {mode} for {label}...")
            try:
                ok, message = installer()
            except Exception as exc:
                handle.finish("failed", exit_detail=str(exc))
                return
            for line in clean_console_output(message).splitlines():
                handle.emit_line(line)
            handle.finish("succeeded" if ok else "failed", exit_detail=None if ok else message)

        job = state.jobs.create(f"tools.{mode}", runner=runner, exclusive_resource=f"tool:{key}")
        return ActionOutcome(job_id=job.job_id)

    return _execute


TOOLS_INSTALL_DESCRIPTOR = ActionDescriptor(
    action_id=TOOLS_INSTALL_ACTION_ID,
    module="tools",
    destructive=False,
    params_schema=_PARAMS_SCHEMA,
    prepare=_prepare_for("install"),
    execute=_execute_for("install"),
    compute_digest=_tools_digest,
)

TOOLS_UPDATE_DESCRIPTOR = ActionDescriptor(
    action_id=TOOLS_UPDATE_ACTION_ID,
    module="tools",
    destructive=False,
    params_schema=_PARAMS_SCHEMA,
    prepare=_prepare_for("update"),
    execute=_execute_for("update"),
    compute_digest=_tools_digest,
)
