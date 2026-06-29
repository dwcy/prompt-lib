# -*- coding: utf-8 -*-
"""Pure rendering + action-availability logic for the MCP Connectors screen.

No Textual or I/O here — just maps an aggregated server dict (from
enumerate_mcp_servers) to display cells and to which action buttons apply.
"""

from __future__ import annotations

import os
from pathlib import Path

_SCOPE_COLOURS = {
    "plugin": "magenta",
    "user": "cyan",
    "local": "blue",
    "project": "yellow",
    "template": "dim",
    "connector": "green",
}

_REMOVABLE = ("user", "local", "project")


def render_scopes(scopes: list[str]) -> str:
    if not scopes:
        return "—"
    return " ".join(
        f"[{_SCOPE_COLOURS.get(s, 'white')}]{s}[/{_SCOPE_COLOURS.get(s, 'white')}]"
        for s in scopes
    )


def removable_scopes(info: dict) -> list[str]:
    """Scopes a server can actually be removed from (server-side connectors can't)."""
    return [s for s in _REMOVABLE if s in info["scopes"]]


def server_row_cells(info: dict) -> tuple[str, str, str, str]:
    """Return (scopes, status, env, command) display cells for one server."""
    if info["is_plugin"]:
        if info.get("plugin_enabled"):
            status = (
                "[green]✓ enabled[/green]"
                if info["active"]
                else "[yellow]✓ enabled (not connected)[/yellow]"
            )
        else:
            status = "[dim]○ disabled[/dim]"
    elif info["active"]:
        status = "[green]✓ connected[/green]"
    elif info.get("pending"):
        status = "[yellow]⏸ pending approval[/yellow]"
    elif info["scopes"] == ["template"]:
        status = "[dim]○ available[/dim]"
    else:
        status = "[yellow]✗ registered, not connected[/yellow]"

    env_required = info.get("env_required") or []
    env = "—"
    if env_required:
        env = " ".join(
            f"{k}[{'green' if os.environ.get(k) else 'red'}]{'✓' if os.environ.get(k) else '✗'}[/]"
            for k in env_required
        )
    cmd = (info.get("command_line") or "—")[:80]
    return render_scopes(info["scopes"]), status, env, cmd


def action_button_states(
    info: dict | None, project_dir: Path | None
) -> tuple[bool, bool, bool, str]:
    """Return (activate_global, activate_local, disable, global_label) for a row.

    Plugins: global button enables the plugin (label flips to "Enable plugin");
    local never applies; disable is offered when the plugin is enabled.
    """
    if not info:
        return (False, False, False, "Activate globally")
    if info["is_plugin"]:
        enabled = bool(info.get("plugin_enabled"))
        label = "Activate globally" if enabled else "Enable plugin"
        return (not enabled, False, enabled, label)
    has_template = "template" in (info.get("definitions") or {})
    scopes = info["scopes"]
    registered_global = "user" in scopes
    registered_project = "project" in scopes
    pending = bool(info.get("pending"))
    # Activate locally writes (+approves) a template, OR approves a project server
    # that is already in .mcp.json but still pending the trust prompt.
    activate_local = project_dir is not None and (
        (has_template and not registered_project) or (registered_project and pending)
    )
    return (
        has_template and not registered_global,
        activate_local,
        bool(removable_scopes(info)),
        "Activate globally",
    )
