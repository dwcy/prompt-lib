# -*- coding: utf-8 -*-
"""Config-deployment action descriptors: config.apply (per-file streamed deploy with
settings backup), config.cleanup (backup + remove extras), config.restore_cleanup, and
config.restore_settings (pre-restore copy). Wraps diff_apply / cleanup_service."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from cabal._paths import TARGET
from cabal.cleanup_service import CLEANUP_BACKUP_DIRNAME, backup_and_remove, restore_cleanup
from cabal.codex_setup.diff_apply import apply_codex_statuses, ensure_codex_target
from cabal.diff_apply import apply_statuses, backup_settings, prune_backups
from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.config_service import config_extras, deploy_digest, extras_digest, resolve_statuses
from cabal.webapi.envelope import ApiError

CONFIG_APPLY_ACTION_ID = "config.apply"
CONFIG_CLEANUP_ACTION_ID = "config.cleanup"
CONFIG_RESTORE_CLEANUP_ACTION_ID = "config.restore_cleanup"
CONFIG_RESTORE_SETTINGS_ACTION_ID = "config.restore_settings"

_APPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "target": {"type": "string", "enum": ["claude", "codex"]},
        "paths": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["target", "paths"],
    "additionalProperties": False,
}
_PATHS_SCHEMA = {
    "type": "object",
    "properties": {"paths": {"type": "array", "items": {"type": "string"}}},
    "required": ["paths"],
    "additionalProperties": False,
}
_BACKUP_ID_SCHEMA = {
    "type": "object",
    "properties": {"backup_id": {"type": "string"}},
    "required": ["backup_id"],
    "additionalProperties": False,
}

_SETTINGS_REL = "settings.json"


# --- config.apply -----------------------------------------------------------


def _apply_prepare(params: dict, _state: Any) -> dict:
    target = params["target"]
    paths = list(params["paths"])
    resolve_statuses(target, paths)  # validates every path exists in the live tree
    backs_up_settings = target == "claude" and _SETTINGS_REL in paths
    return {
        "summary": f"Deploy {len(paths)} file(s) to the {target} target",
        "commands": [],
        "files_changed": paths,
        "scopes": [target],
        "backup": "settings.json backup" if backs_up_settings else None,
        "removals": [],
    }


def _apply_execute(params: dict, state: Any) -> ActionOutcome:
    target = params["target"]
    paths = list(params["paths"])

    def runner(handle) -> None:
        resolved = resolve_statuses(target, paths)
        if target == "claude" and _SETTINGS_REL in paths:
            if backup_settings() is not None:
                handle.emit_line("Backed up existing settings.json")
        elif target == "codex":
            ensure_codex_target()
        apply_one = apply_statuses if target == "claude" else apply_codex_statuses
        for status, path in resolved:
            apply_one([status])
            handle.emit_line(f"Deployed {path} ({status.state.lower()})")
        if target == "claude":
            prune_backups()
        handle.finish("succeeded")

    job = state.jobs.create(CONFIG_APPLY_ACTION_ID, runner=runner, exclusive_resource=f"config-apply:{target}")
    return ActionOutcome(job_id=job.job_id)


# --- config.cleanup ---------------------------------------------------------


def _validated_cleanup_paths(raw_paths: list[str]) -> list[str]:
    available = {
        extra["rel_path"]
        for group in config_extras("claude")["groups"]
        for extra in group["extras"]
    }
    paths = list(dict.fromkeys(raw_paths))
    unknown = [path for path in paths if path not in available]
    if unknown:
        raise ApiError(422, "params_invalid", f"Not a current config extra: {unknown[0]!r}")
    return paths


def _cleanup_prepare(params: dict, _state: Any) -> dict:
    paths = _validated_cleanup_paths(params["paths"])
    return {
        "summary": f"Remove {len(paths)} extra file(s) from the ~/.claude target",
        "commands": [],
        "files_changed": paths,
        "scopes": ["claude"],
        "backup": "cleanup backup",
        "removals": paths,
    }


def _cleanup_execute(params: dict, _state: Any) -> ActionOutcome:
    paths = _validated_cleanup_paths(params["paths"])
    abs_paths = [TARGET / rel for rel in paths]
    result = backup_and_remove(abs_paths, target=TARGET)
    return ActionOutcome(
        data={
            "backup_dir": result.backup_dir.name if result.backup_dir is not None else None,
            "backed_up": [str(p) for p in result.backed_up],
            "deleted": [str(p) for p in result.deleted],
            "errors": {str(k): v for k, v in result.errors.items()},
        }
    )


# --- config.restore_cleanup -------------------------------------------------


def _cleanup_backup_path(backup_id: str) -> Path:
    if not backup_id or Path(backup_id).name != backup_id:
        raise ApiError(422, "params_invalid", "backup_id must be a cleanup backup name")
    root = (TARGET / CLEANUP_BACKUP_DIRNAME).resolve()
    backup_dir = (root / backup_id).resolve()
    if backup_dir.parent != root or not backup_dir.is_dir():
        raise ApiError(404, "backup_not_found", f"Unknown cleanup backup {backup_id!r}")
    return backup_dir


def _restore_cleanup_prepare(params: dict, _state: Any) -> dict:
    _cleanup_backup_path(params["backup_id"])
    return {
        "summary": f"Restore files from cleanup backup {params['backup_id']}",
        "commands": [],
        "files_changed": [],
        "scopes": ["claude"],
        "backup": None,
        "removals": [],
    }


def _restore_cleanup_execute(params: dict, _state: Any) -> ActionOutcome:
    backup_dir = _cleanup_backup_path(params["backup_id"])
    result = restore_cleanup(backup_dir, target=TARGET)
    return ActionOutcome(
        data={
            "restored": [str(p) for p in result.restored],
            "skipped": [[str(p), reason] for p, reason in result.skipped],
            "errors": {str(k): v for k, v in result.errors.items()},
        }
    )


# --- config.restore_settings ------------------------------------------------


def _settings_backup_path(backup_id: str) -> Path:
    if not backup_id or Path(backup_id).name != backup_id or not backup_id.startswith("settings.json.bak."):
        raise ApiError(422, "params_invalid", "backup_id must be a settings.json backup name")
    source = (TARGET / backup_id).resolve()
    if source.parent != TARGET.resolve() or not source.is_file():
        raise ApiError(404, "backup_not_found", f"Unknown settings backup {backup_id!r}")
    return source


def _restore_settings_prepare(params: dict, _state: Any) -> dict:
    _settings_backup_path(params["backup_id"])
    return {
        "summary": f"Restore settings.json from {params['backup_id']} (a pre-restore copy is made first)",
        "commands": [],
        "files_changed": ["settings.json"],
        "scopes": ["claude"],
        "backup": "pre-restore settings.json backup",
        "removals": [],
    }


def _restore_settings_execute(params: dict, _state: Any) -> ActionOutcome:
    source = _settings_backup_path(params["backup_id"])
    pre_restore = backup_settings()
    shutil.copy2(source, TARGET / "settings.json")
    return ActionOutcome(
        data={
            "restored_from": source.name,
            "pre_restore_backup": pre_restore.name if pre_restore is not None else None,
        }
    )


CONFIG_APPLY_DESCRIPTOR = ActionDescriptor(
    action_id=CONFIG_APPLY_ACTION_ID,
    module="config_deploy",
    destructive=False,
    backup_policy="settings_backup",
    params_schema=_APPLY_SCHEMA,
    prepare=_apply_prepare,
    execute=_apply_execute,
    compute_digest=lambda params, _state: deploy_digest(params["target"]),
)

CONFIG_CLEANUP_DESCRIPTOR = ActionDescriptor(
    action_id=CONFIG_CLEANUP_ACTION_ID,
    module="cleanup_restore",
    destructive=True,
    backup_policy="cleanup_backup",
    params_schema=_PATHS_SCHEMA,
    prepare=_cleanup_prepare,
    execute=_cleanup_execute,
    compute_digest=lambda _params, _state: extras_digest("claude"),
)

CONFIG_RESTORE_CLEANUP_DESCRIPTOR = ActionDescriptor(
    action_id=CONFIG_RESTORE_CLEANUP_ACTION_ID,
    module="cleanup_restore",
    destructive=False,
    backup_policy=None,
    params_schema=_BACKUP_ID_SCHEMA,
    prepare=_restore_cleanup_prepare,
    execute=_restore_cleanup_execute,
)

CONFIG_RESTORE_SETTINGS_DESCRIPTOR = ActionDescriptor(
    action_id=CONFIG_RESTORE_SETTINGS_ACTION_ID,
    module="cleanup_restore",
    destructive=False,
    backup_policy="settings_backup",
    params_schema=_BACKUP_ID_SCHEMA,
    prepare=_restore_settings_prepare,
    execute=_restore_settings_execute,
)

CONFIG_DESCRIPTORS = (
    CONFIG_APPLY_DESCRIPTOR,
    CONFIG_CLEANUP_DESCRIPTOR,
    CONFIG_RESTORE_CLEANUP_DESCRIPTOR,
    CONFIG_RESTORE_SETTINGS_DESCRIPTOR,
)
