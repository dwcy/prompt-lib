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
    add_template_to_project_mcp,
    approve_project_mcp,
    claude_mcp_add_from_template,
    claude_mcp_remove,
    claude_plugin_set_enabled,
    enumerate_mcp_servers,
    remove_from_project_mcp,
)
from cabal.mcp_view_logic import (
    action_button_states,
    removable_scopes,
    server_row_cells,
)
from cabal.widgets.disable_scope_modal import DisableScopeModal
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
        Binding("g", "activate_global", "Activate globally"),
        Binding("l", "activate_local", "Activate locally"),
        Binding("d", "disable", "Disable"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ MCP Connectors ✦[/bold bright_magenta]\n"
                "[dim]Every known MCP server across scopes. Activate globally = `claude mcp add -s user` · "
                "Activate Locally = write into this project's .mcp.json + approve it (also approves a pending one) · Disable = remove / disable plugin.[/dim]\n"
                "[dim]Scopes: plugin (marketplace) · user (~/.claude.json, all projects) · local (this project only) · "
                "project (.mcp.json) · template (defined here, not registered) · connector (claude.ai / remote, server-side).[/dim]",
                classes="panel",
            )
            yield DataTable(
                id="mcp-table", show_cursor=True, cursor_type="row", zebra_stripes=True
            )
            with Horizontal():
                yield Button(
                    "Activate globally", id="mcp-act-global", variant="success"
                )
                yield Button("Activate Locally", id="mcp-act-local", variant="primary")
                yield Button("Disable", id="mcp-disable", variant="error")
                yield Button("Refresh (Ctrl+R)", id="mcp-refresh")
                yield Button("Back (Esc)", id="mcp-back")
            yield Static("", id="mcp-status", classes="panel")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._servers: dict[str, dict] = {}
        self._project_dir = self._resolve_project_dir()
        tbl = self.query_one("#mcp-table", DataTable)
        tbl.add_columns("Name", "Scope(s)", "Status", "Env", "Command")
        self._set_action_buttons(False, False, False)
        self._refresh()

    def _resolve_project_dir(self) -> Path | None:
        getter = getattr(self.app, "project_path", None)
        try:
            return getter() if callable(getter) else None
        except Exception:
            return None

    def _refresh(self) -> None:
        self.query_one("#mcp-table", DataTable).loading = True
        self.query_one("#mcp-status", Static).update(
            "[dim italic]Listing MCP servers — `claude mcp list` can take up to 60s…[/]"
        )
        self.run_worker(self._load, thread=True, exclusive=True)

    def _load(self) -> None:
        try:
            aggregated = enumerate_mcp_servers(project_dir=self._project_dir)
        except Exception as e:
            self.app.call_from_thread(self._on_load_error, str(e))
            return
        self.app.call_from_thread(self._apply_servers, aggregated)

    def _on_load_error(self, msg: str) -> None:
        self.query_one("#mcp-status", Static).update(
            f"[red]Error enumerating: {msg}[/red]"
        )
        self.query_one("#mcp-table", DataTable).loading = False

    def _apply_servers(self, aggregated: dict[str, dict]) -> None:
        self._servers = aggregated
        tbl = self.query_one("#mcp-table", DataTable)
        tbl.clear()
        for name in sorted(aggregated.keys()):
            cells = server_row_cells(aggregated[name])
            tbl.add_row(name, *cells, key=name)
        local = self._project_dir or Path.cwd()
        self.query_one("#mcp-status", Static).update(
            f"[dim]{tbl.row_count} servers shown. Local activation writes to {local / '.mcp.json'}.[/dim]"
        )
        tbl.loading = False
        self._sync_action_buttons()

    def action_refresh(self) -> None:
        self._refresh()

    def action_activate_global(self) -> None:
        self._activate_global()

    def action_activate_local(self) -> None:
        self._activate_local()

    def action_disable(self) -> None:
        self._disable()

    # --- selection / button state -------------------------------------------

    def _current_name(self) -> str | None:
        tbl = self.query_one("#mcp-table", DataTable)
        if tbl.row_count == 0 or tbl.cursor_row is None:
            return None
        try:
            return tbl.coordinate_to_cell_key((tbl.cursor_row, 0)).row_key.value
        except Exception:
            return None

    def _set_action_buttons(self, g: bool, l: bool, d: bool) -> None:
        self.query_one("#mcp-act-global", Button).disabled = not g
        self.query_one("#mcp-act-local", Button).disabled = not l
        self.query_one("#mcp-disable", Button).disabled = not d

    def _sync_action_buttons(self) -> None:
        info = self._servers.get(self._current_name() or "")
        g, l, d, label = action_button_states(info, self._project_dir)
        self.query_one("#mcp-act-global", Button).label = label
        self._set_action_buttons(g, l, d)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._sync_action_buttons()

    # --- actions -------------------------------------------------------------

    def _status(self, msg: str) -> None:
        self.query_one("#mcp-status", Static).update(msg)

    def _activate_global(self) -> None:
        info = self._servers.get(self._current_name() or "")
        if not info:
            return
        name = self._current_name()
        if info["is_plugin"]:
            pid = info.get("plugin_id")
            if not pid:
                self._status("[yellow]Plugin id unknown — manage via /plugin.[/yellow]")
                return
            if info.get("plugin_enabled"):
                self._status(f"[dim]{name} already enabled.[/dim]")
                return
            ok, msg = claude_plugin_set_enabled(
                pid, True, scope=info.get("plugin_scope")
            )
            self._status(
                f"[{'green' if ok else 'red'}]{'✓ enabled' if ok else '✗'} {pid}: {msg}[/]"
            )
            self._refresh()
            return
        tmpl = (info.get("definitions") or {}).get("template")
        if not tmpl:
            self._status(
                f"[red]No template for {name} — add via `claude mcp add`.[/red]"
            )
            return
        ok, msg = claude_mcp_add_from_template(name, tmpl)
        self._status(
            f"[{'green' if ok else 'red'}]{'✓ added (user)' if ok else '✗ add failed'} {name}: {msg}[/]"
        )
        self._refresh()

    def _activate_local(self) -> None:
        name = self._current_name()
        info = self._servers.get(name or "")
        if not info:
            return
        if info["is_plugin"]:
            self._status(
                "[yellow]Plugins can't be added at project scope — use /plugin.[/yellow]"
            )
            return
        if self._project_dir is None:
            self._status(
                "[yellow]No project directory to write .mcp.json into.[/yellow]"
            )
            return
        # Already in .mcp.json but pending the trust prompt → just approve it.
        if "project" in info["scopes"] and info.get("pending"):
            ok, msg = approve_project_mcp(name, self._project_dir)
            self._status(f"[{'green' if ok else 'red'}]{'✓' if ok else '✗'} {msg}[/]")
            self._refresh()
            return
        tmpl = (info.get("definitions") or {}).get("template")
        if not tmpl:
            self._status(
                f"[red]No template for {name} — cannot register at project scope.[/red]"
            )
            return
        ok, msg = add_template_to_project_mcp(name, tmpl, self._project_dir)
        self._status(f"[{'green' if ok else 'red'}]{'✓' if ok else '✗'} {msg}[/]")
        self._refresh()

    def _disable(self) -> None:
        name = self._current_name()
        info = self._servers.get(name or "")
        if not info:
            return
        if info["is_plugin"]:
            pid = info.get("plugin_id")
            if not pid:
                self._status("[yellow]Plugin id unknown — manage via /plugin.[/yellow]")
                return
            ok, msg = claude_plugin_set_enabled(
                pid, False, scope=info.get("plugin_scope")
            )
            self._status(
                f"[{'green' if ok else 'red'}]{'✓ disabled' if ok else '✗'} {pid}: {msg}[/]"
            )
            self._refresh()
            return
        scopes = removable_scopes(info)
        if not scopes:
            self._status(
                f"[yellow]{name} has no removable scope (server-side connector?).[/yellow]"
            )
            return
        if len(scopes) == 1:
            self._remove_scope(name, scopes[0])
            return
        self.app.push_screen(
            DisableScopeModal(name, scopes),
            lambda scope: self._remove_scope(name, scope) if scope else None,
        )

    def _remove_scope(self, name: str, scope: str) -> None:
        if scope == "project":
            ok, msg = remove_from_project_mcp(name, self._project_dir or Path.cwd())
        else:
            ok, msg = claude_mcp_remove(name, scope)
        self._status(
            f"[{'green' if ok else 'red'}]{'✓ disabled' if ok else '✗ failed'} {name} ({scope}): {msg}[/]"
        )
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "mcp-back":
            self.app.pop_screen()
        elif bid == "mcp-refresh":
            self._refresh()
        elif bid == "mcp-act-global":
            self._activate_global()
        elif bid == "mcp-act-local":
            self._activate_local()
        elif bid == "mcp-disable":
            self._disable()
