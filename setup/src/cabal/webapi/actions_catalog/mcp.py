# -*- coding: utf-8 -*-
"""MCP connector action descriptors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cabal.mcp_ops import (
    add_template_to_project_mcp,
    approve_project_mcp,
    claude_mcp_add_from_template,
    claude_mcp_remove,
    claude_plugin_set_enabled,
    enumerate_mcp_servers,
    remove_from_project_mcp,
)
from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.envelope import ApiError
from cabal.webapi.mcp_service import mcp_digest, project_dir

_NAME_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "required": ["name"],
    "additionalProperties": False,
}

_DISABLE_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "scope": {"type": ["string", "null"]}},
    "required": ["name"],
    "additionalProperties": False,
}


def _servers(state: Any) -> dict[str, dict]:
    return enumerate_mcp_servers(project_dir=project_dir(state))


def _require_info(params: dict, state: Any) -> tuple[str, dict]:
    name = params["name"]
    info = _servers(state).get(name)
    if info is None:
        raise ApiError(422, "params_invalid", f"Unknown MCP server {name!r}")
    return name, info


def _project(state: Any) -> Path:
    project = project_dir(state)
    if project is None:
        raise ApiError(422, "params_invalid", "Select a project before using project-scoped MCP actions")
    return project


def _activate_global_prepare(params: dict, state: Any) -> dict:
    name, info = _require_info(params, state)
    if info.get("is_plugin"):
        return {
            "summary": f"Enable MCP plugin {info.get('plugin_id') or name}",
            "commands": ["claude plugin enable"],
            "files_changed": [],
            "scopes": ["mcp", "plugin"],
            "backup": None,
            "removals": [],
        }
    return {
        "summary": f"Activate {name} globally",
        "commands": ["claude mcp add -s user"],
        "files_changed": [str(Path.home() / ".claude.json")],
        "scopes": ["mcp", "user"],
        "backup": None,
        "removals": [],
    }


def _activate_global_execute(params: dict, state: Any) -> ActionOutcome:
    name, info = _require_info(params, state)
    if info.get("is_plugin"):
        plugin_id = info.get("plugin_id")
        if not plugin_id:
            raise ApiError(422, "params_invalid", f"Plugin id unknown for {name!r}")
        ok, message = claude_plugin_set_enabled(plugin_id, True, scope=info.get("plugin_scope"))
    else:
        template = (info.get("definitions") or {}).get("template")
        if not template:
            raise ApiError(422, "params_invalid", f"No template for {name!r}")
        ok, message = claude_mcp_add_from_template(name, template)
    if not ok:
        raise ApiError(500, "execution_failed", message)
    return ActionOutcome(data={"message": message, "server": name})


def _activate_local_prepare(params: dict, state: Any) -> dict:
    name, _info = _require_info(params, state)
    project = _project(state)
    return {
        "summary": f"Activate {name} for this project",
        "commands": ["write .mcp.json", "approve project MCP server"],
        "files_changed": [str(project / ".mcp.json"), str(Path.home() / ".claude.json")],
        "scopes": ["mcp", "project"],
        "backup": None,
        "removals": [],
    }


def _activate_local_execute(params: dict, state: Any) -> ActionOutcome:
    name, info = _require_info(params, state)
    project = _project(state)
    if "project" in (info.get("scopes") or []) and info.get("pending"):
        ok, message = approve_project_mcp(name, project)
    else:
        template = (info.get("definitions") or {}).get("template")
        if not template:
            raise ApiError(422, "params_invalid", f"No template for {name!r}")
        ok, message = add_template_to_project_mcp(name, template, project)
    if not ok:
        raise ApiError(500, "execution_failed", message)
    return ActionOutcome(data={"message": message, "server": name})


def _approve_prepare(params: dict, state: Any) -> dict:
    name, _info = _require_info(params, state)
    project = _project(state)
    return {
        "summary": f"Approve pending MCP server {name}",
        "commands": ["update enabledMcpjsonServers"],
        "files_changed": [str(Path.home() / ".claude.json"), str(project / ".mcp.json")],
        "scopes": ["mcp", "project"],
        "backup": None,
        "removals": [],
    }


def _approve_execute(params: dict, state: Any) -> ActionOutcome:
    name, _info = _require_info(params, state)
    ok, message = approve_project_mcp(name, _project(state))
    if not ok:
        raise ApiError(500, "execution_failed", message)
    return ActionOutcome(data={"message": message, "server": name})


def _disable_prepare(params: dict, state: Any) -> dict:
    name, info = _require_info(params, state)
    scope = params.get("scope")
    if info.get("is_plugin"):
        removal = str(info.get("plugin_id") or name)
        target_scope = "plugin"
    else:
        removable = list(info.get("scopes") or [])
        if scope is None:
            from cabal.mcp_view_logic import removable_scopes

            scopes = removable_scopes(info)
            if len(scopes) != 1:
                raise ApiError(422, "params_invalid", "Disable requires a scope when multiple scopes are removable")
            scope = scopes[0]
        if scope not in removable:
            raise ApiError(422, "params_invalid", f"{name!r} is not registered in scope {scope!r}")
        target_scope = str(scope)
        removal = f"{name} ({target_scope})"
    return {
        "summary": f"Disable MCP server {removal}",
        "commands": ["claude mcp remove" if target_scope != "project" else "remove from .mcp.json"],
        "files_changed": [str(Path.home() / ".claude.json")],
        "scopes": ["mcp", target_scope],
        "backup": "No backup; re-enable or re-register the MCP server to recover",
        "removals": [removal],
    }


def _disable_execute(params: dict, state: Any) -> ActionOutcome:
    name, info = _require_info(params, state)
    if info.get("is_plugin"):
        plugin_id = info.get("plugin_id")
        if not plugin_id:
            raise ApiError(422, "params_invalid", f"Plugin id unknown for {name!r}")
        ok, message = claude_plugin_set_enabled(plugin_id, False, scope=info.get("plugin_scope"))
    else:
        scope = params.get("scope")
        if scope == "project":
            ok, message = remove_from_project_mcp(name, _project(state))
        elif isinstance(scope, str):
            ok, message = claude_mcp_remove(name, scope)
        else:
            raise ApiError(422, "params_invalid", "Disable requires a scope")
    if not ok:
        raise ApiError(500, "execution_failed", message)
    return ActionOutcome(data={"message": message, "server": name})


MCP_ACTIVATE_GLOBAL_DESCRIPTOR = ActionDescriptor(
    action_id="mcp.activate_global",
    module="mcp",
    destructive=False,
    params_schema=_NAME_SCHEMA,
    prepare=_activate_global_prepare,
    execute=_activate_global_execute,
    compute_digest=lambda params, state: mcp_digest(state, params["name"]),
)

MCP_ACTIVATE_LOCAL_DESCRIPTOR = ActionDescriptor(
    action_id="mcp.activate_local",
    module="mcp",
    destructive=False,
    params_schema=_NAME_SCHEMA,
    prepare=_activate_local_prepare,
    execute=_activate_local_execute,
    compute_digest=lambda params, state: mcp_digest(state, params["name"]),
)

MCP_APPROVE_DESCRIPTOR = ActionDescriptor(
    action_id="mcp.approve",
    module="mcp",
    destructive=False,
    params_schema=_NAME_SCHEMA,
    prepare=_approve_prepare,
    execute=_approve_execute,
    compute_digest=lambda params, state: mcp_digest(state, params["name"]),
)

MCP_DISABLE_DESCRIPTOR = ActionDescriptor(
    action_id="mcp.disable",
    module="mcp",
    destructive=True,
    params_schema=_DISABLE_SCHEMA,
    prepare=_disable_prepare,
    execute=_disable_execute,
    compute_digest=lambda params, state: mcp_digest(state, params["name"]),
)

MCP_DESCRIPTORS = (
    MCP_ACTIVATE_GLOBAL_DESCRIPTOR,
    MCP_ACTIVATE_LOCAL_DESCRIPTOR,
    MCP_APPROVE_DESCRIPTOR,
    MCP_DISABLE_DESCRIPTOR,
)
