# -*- coding: utf-8 -*-
"""Web payloads for MCP connector state and action previews."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from cabal.mcp_ops import enumerate_mcp_servers, enumerate_one_server
from cabal.mcp_view_logic import action_button_states, removable_scopes
from cabal.webapi.envelope import compute_precondition_digest


def project_dir(state: Any) -> Path | None:
    project = getattr(state, "project", None)
    return Path(project) if project is not None else None


def _status(info: dict) -> str:
    if info.get("is_plugin") and not info.get("plugin_enabled", True):
        return "inactive"
    if info.get("active"):
        return "connected"
    if info.get("pending"):
        return "pending"
    if info.get("scopes") == ["template"]:
        return "inactive"
    return "error"


def _env_status(info: dict) -> list[dict[str, Any]]:
    return [
        {"name": name, "present": bool(os.environ.get(name))}
        for name in (info.get("env_required") or [])
    ]


def _row(name: str, info: dict, project: Path | None) -> dict[str, Any]:
    can_global, can_local, can_disable, global_label = action_button_states(info, project)
    actions = []
    if can_global:
        actions.append("activate_global")
    if can_local:
        actions.append("activate_local")
    if info.get("pending") and "project" in (info.get("scopes") or []):
        actions.append("approve")
    if can_disable:
        actions.append("disable")
    return {
        "name": name,
        "scopes": list(info.get("scopes") or []),
        "status": _status(info),
        "active": bool(info.get("active")),
        "pending": bool(info.get("pending")),
        "command": str(info.get("command_line") or ""),
        "env_required": list(info.get("env_required") or []),
        "env_status": _env_status(info),
        "env_present": all(item["present"] for item in _env_status(info)),
        "is_plugin": bool(info.get("is_plugin")),
        "plugin_id": info.get("plugin_id"),
        "plugin_enabled": info.get("plugin_enabled"),
        "plugin_scope": info.get("plugin_scope"),
        "removable_scopes": removable_scopes(info),
        "actions_available": actions,
        "global_action_label": global_label,
    }


def list_mcp_payload(state: Any) -> dict[str, Any]:
    project = project_dir(state)
    servers = enumerate_mcp_servers(project_dir=project)
    rows = [_row(name, servers[name], project) for name in sorted(servers)]
    counts = {
        "total": len(rows),
        "connected": sum(1 for row in rows if row["status"] == "connected"),
        "pending": sum(1 for row in rows if row["status"] == "pending"),
        "inactive": sum(1 for row in rows if row["status"] == "inactive"),
        "error": sum(1 for row in rows if row["status"] == "error"),
    }
    return {
        "servers": rows,
        "counts": counts,
        "project_dir": str(project) if project is not None else None,
    }


def mcp_row_payload(state: Any, name: str) -> dict[str, Any]:
    project = project_dir(state)
    info = enumerate_one_server(name, project_dir=project)
    if info is None:
        return {"server": None, "project_dir": str(project) if project is not None else None}
    return {"server": _row(name, info, project), "project_dir": str(project) if project is not None else None}


def mcp_digest(state: Any, name: str | None = None) -> str:
    project = project_dir(state)
    if name:
        payload = mcp_row_payload(state, name)
    else:
        payload = list_mcp_payload(state)
    return compute_precondition_digest(payload)
