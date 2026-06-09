# -*- coding: utf-8 -*-
"""McpScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

from __future__ import annotations

import filecmp
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from rich.markup import escape as escape_markup
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import (
    Center,
    Container,
    Horizontal,
    ScrollableContainer,
    Vertical,
    VerticalScroll,
)
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    MarkdownViewer,
    OptionList,
    RadioButton,
    RadioSet,
    Rule,
    Select,
    Static,
)
from textual.widgets.option_list import Option
from textual.widget import Widget

from cabal._paths import GLOBAL_DIR, TARGET, REPO_DIR, ENV_DIR, ENV_FILE, RESOURCE_ROOT
from cabal.app_widgets import AppHeader
from cabal.banner import HexBanner, render_banner
from cabal.components import COMPONENTS, Component, ENV_DESCRIPTIONS, FileStatus
from cabal.diff_apply import (
    apply_statuses,
    backup_settings,
    diff_component,
    find_extras,
    prune_backups,
)
from cabal.env_detect import detect_env, find_env_vars
from cabal.env_summary import render_env_summary
from cabal.git_config import apply_git_line_endings, recommended_autocrlf
from cabal.installers.gh import gh_device_init, gh_device_poll, gh_fetch_token
from cabal.mcp_ops import (
    claude_mcp_add_from_template,
    claude_mcp_remove,
    claude_plugin_set_enabled,
    enumerate_mcp_servers,
)
from cabal.tools import (
    ENV_INSTALLERS,
    ENV_TOOL_GROUPS,
    TOOLS,
    Tool,
    VERSION_FLOORS,
    WINGET_IDS,
    _below_floor,
    _installer_for,
    _outdated_packages,
    _probe_key,
)
from cabal.updates import check_for_updates, do_git_pull
from cabal.widgets.env_panel import EnvPanel
from cabal.widgets.update_panel import UpdatePanel


class McpScreen(Screen):
    """Unified MCP view across all scopes (plugin/user/local/project/template).

    Live status from `claude mcp list`. Toggle enables/disables via `claude mcp add/remove`.
    Settings.json `mcpServers` is dead — Claude Code does not read it. See add-mcp skill.
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("space", "toggle", "Toggle"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Global MCP servers ✦[/bold bright_magenta]\n"
                "[dim]Global (user-scope) + Claude plugin servers, incl. ones not added here. Toggle = `claude mcp add -s user` (from template) or `claude mcp remove`.[/dim]\n"
                "[dim]Scopes: plugin (marketplace) · user (~/.claude.json, all projects) · local (this project only) · "
                "project (.mcp.json) · template (defined here, not registered) · connector (claude.ai / remote, server-side).[/dim]",
                classes="panel",
            )
            yield DataTable(
                id="mcp-table", show_cursor=True, cursor_type="row", zebra_stripes=True
            )
            with Horizontal():
                yield Button("Toggle (Space)", id="mcp-toggle", variant="primary")
                yield Button("Refresh (Ctrl+R)", id="mcp-refresh")
                yield Button("Back (Esc)", id="mcp-back")
            yield Static("", id="mcp-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#mcp-table", DataTable)
        tbl.add_columns("Name", "Scope(s)", "Status", "Env", "Command")
        self._refresh()

    def _refresh(self) -> None:
        self.loading = True
        self.query_one("#mcp-status", Static).update(
            "[dim italic]Listing MCP servers — `claude mcp list` can take up to 60s…[/]"
        )
        self.run_worker(self._load, thread=True, exclusive=True)

    def _load(self) -> None:
        try:
            aggregated = enumerate_mcp_servers()
        except Exception as e:
            self.app.call_from_thread(self._on_load_error, str(e))
            return
        self.app.call_from_thread(self._apply_servers, aggregated)

    def _on_load_error(self, msg: str) -> None:
        self.query_one("#mcp-status", Static).update(
            f"[red]Error enumerating: {msg}[/red]"
        )
        self.loading = False

    def _apply_servers(self, aggregated: dict[str, dict]) -> None:
        tbl = self.query_one("#mcp-table", DataTable)
        tbl.clear()
        for name in sorted(aggregated.keys()):
            info = aggregated[name]
            scopes_disp = _render_scopes(info["scopes"])
            if info["is_plugin"]:
                if info.get("plugin_enabled"):
                    status_disp = (
                        "[green]✓ enabled[/green]"
                        if info["active"]
                        else "[yellow]✓ enabled (not connected)[/yellow]"
                    )
                else:
                    status_disp = "[dim]○ disabled[/dim]"
            elif info["active"]:
                status_disp = "[green]✓ connected[/green]"
            elif info["scopes"] == ["template"]:
                status_disp = "[dim]○ available[/dim]"
            else:
                status_disp = "[yellow]✗ registered, not connected[/yellow]"
            env_disp = "—"
            if info["env_required"]:
                env_disp = " ".join(
                    f"{k}[{'green' if os.environ.get(k) else 'red'}]{'✓' if os.environ.get(k) else '✗'}[/]"
                    for k in info["env_required"]
                )
            cmd_disp = (info["command_line"] or "—")[:80]
            tbl.add_row(name, scopes_disp, status_disp, env_disp, cmd_disp, key=name)
        self.query_one("#mcp-status", Static).update(
            f"[dim]{tbl.row_count} servers shown. Space toggles — templates add/remove, plugins enable/disable.[/dim]"
        )
        self.loading = False

    def action_refresh(self) -> None:
        self._refresh()

    def action_toggle(self) -> None:
        self._toggle_selected()

    def _toggle_selected(self) -> None:
        tbl = self.query_one("#mcp-table", DataTable)
        status_label = self.query_one("#mcp-status", Static)
        if tbl.cursor_row is None or tbl.row_count == 0:
            return
        row_key = tbl.coordinate_to_cell_key((tbl.cursor_row, 0)).row_key.value
        if not row_key:
            return
        name = row_key
        info = enumerate_mcp_servers().get(name)
        if not info:
            status_label.update(f"[red]Not found: {name}[/red]")
            return
        if info["is_plugin"]:
            pid = info.get("plugin_id")
            if not pid:
                status_label.update(
                    "[yellow]Plugin id unknown — manage via /plugin in Claude Code.[/yellow]"
                )
                return
            enable = not bool(info.get("plugin_enabled"))
            ok, msg = claude_plugin_set_enabled(
                pid, enable, scope=info.get("plugin_scope")
            )
            verb = "enabled" if enable else "disabled"
            icon = "✓" if ok else "✗"
            colour = "green" if ok else "red"
            status_label.update(f"[{colour}]{icon} {verb} {pid}: {msg}[/]")
            self._refresh()
            return
        active_scopes = [s for s in info["scopes"] if s in ("user", "local")]
        if active_scopes:
            scope = active_scopes[0]
            ok, msg = claude_mcp_remove(name, scope)
            status_label.update(
                f"[{'green' if ok else 'red'}]{'✓ removed' if ok else '✗ remove failed'} {name} ({scope}): {msg}[/]"
            )
        else:
            tmpl = info["definitions"].get("template")
            if not tmpl:
                status_label.update(
                    f"[red]No template for {name} — add manually via `claude mcp add`[/red]"
                )
                return
            ok, msg = claude_mcp_add_from_template(name, tmpl)
            status_label.update(
                f"[{'green' if ok else 'red'}]{'✓ added' if ok else '✗ add failed'} {name} (user): {msg}[/]"
            )
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "mcp-back":
            self.app.pop_screen()
        elif bid == "mcp-refresh":
            self._refresh()
        elif bid == "mcp-toggle":
            self._toggle_selected()


_SCOPE_COLOURS = {
    "plugin": "magenta",
    "user": "cyan",
    "local": "blue",
    "project": "yellow",
    "template": "dim",
    "connector": "green",
}


def _render_scopes(scopes: list[str]) -> str:
    if not scopes:
        return "—"
    out = []
    for s in scopes:
        c = _SCOPE_COLOURS.get(s, "white")
        out.append(f"[{c}]{s}[/{c}]")
    return " ".join(out)
