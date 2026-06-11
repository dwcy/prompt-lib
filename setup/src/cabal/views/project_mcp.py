# -*- coding: utf-8 -*-
"""ProjectMcpScreen — edits <target_dir>/.mcp.json. Plugin/user rows are read-only."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.mcp_ops import (
    add_template_to_project_mcp,
    enumerate_mcp_servers,
    read_project_mcp,
    remove_from_project_mcp,
)

_SCOPE_COLOURS = {
    "plugin": "magenta",
    "user": "cyan",
    "local": "blue",
    "project": "yellow",
    "template": "dim",
}


def _render_scopes(scopes: list[str]) -> str:
    if not scopes:
        return "—"
    out = []
    for s in scopes:
        c = _SCOPE_COLOURS.get(s, "white")
        out.append(f"[{c}]{s}[/{c}]")
    return " ".join(out)


class ProjectMcpScreen(Screen):
    """Per-project .mcp.json editor. Reuses enumerate_mcp_servers(); locks plugin/user rows."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("space", "toggle", "Toggle"),
    ]

    def __init__(
        self, target_dir: Path, on_change: Callable[[int], None] | None = None
    ) -> None:
        super().__init__()
        self._target_dir = target_dir
        self._on_change = on_change

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Project MCP ✦[/bold bright_magenta]\n"
                f"[dim]Writes to {self._target_dir / '.mcp.json'}. Plugin and user scopes are read-only here.[/dim]",
                classes="panel",
            )
            yield DataTable(
                id="pmcp-table", show_cursor=True, cursor_type="row", zebra_stripes=True
            )
            with Horizontal():
                yield Button("Toggle (Space)", id="pmcp-toggle", variant="primary")
                yield Button("Refresh (Ctrl+R)", id="pmcp-refresh")
                yield Button("Back (Esc)", id="pmcp-back")
            yield Static("", id="pmcp-status", classes="panel")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        tbl = self.query_one("#pmcp-table", DataTable)
        tbl.add_columns("Name", "Scope(s)", "Editable", "Env", "Command")
        self._refresh()

    def _refresh(self) -> None:
        self.loading = True
        self.query_one("#pmcp-status", Static).update(
            "[dim italic]Listing MCP servers — `claude mcp list` can take up to 60s…[/]"
        )
        self.run_worker(self._load, thread=True, exclusive=True)

    def _load(self) -> None:
        try:
            agg = enumerate_mcp_servers(project_dir=self._target_dir)
            proj_entries = read_project_mcp(self._target_dir)
        except Exception as e:
            self.app.call_from_thread(self._on_load_error, str(e))
            return
        self.app.call_from_thread(self._apply_servers, agg, proj_entries)

    def _on_load_error(self, msg: str) -> None:
        self.query_one("#pmcp-status", Static).update(
            f"[red]Error enumerating: {msg}[/red]"
        )
        self.loading = False

    def _apply_servers(self, aggregated: dict[str, dict], proj_entries: dict) -> None:
        tbl = self.query_one("#pmcp-table", DataTable)
        tbl.clear()
        for name in sorted(aggregated.keys()):
            info = aggregated[name]
            scopes = info["scopes"]
            in_project_file = name in proj_entries
            editable = (("project" in scopes) or ("template" in scopes)) and not info[
                "is_plugin"
            ]
            if in_project_file:
                editable = True
            if info["is_plugin"]:
                editable = False
            editable_label = (
                "[green]✓[/green]" if editable else "[dim](read-only)[/dim]"
            )
            env_required = info.get("env_required") or []
            env_disp = (
                "—"
                if not env_required
                else " ".join(
                    f"{k}[{'green' if os.environ.get(k) else 'red'}]{'✓' if os.environ.get(k) else '✗'}[/]"
                    for k in env_required
                )
            )
            scopes_for_render = list(scopes)
            if in_project_file and "project" not in scopes_for_render:
                scopes_for_render.append("project")
            cmd_disp = (info.get("command_line") or "—")[:80]
            tbl.add_row(
                name,
                _render_scopes(scopes_for_render),
                editable_label,
                env_disp,
                cmd_disp,
                key=name,
            )
        self.query_one("#pmcp-status", Static).update(
            f"[dim]{tbl.row_count} servers shown. Space toggles editable rows. Writes to {self._target_dir / '.mcp.json'}.[/dim]"
        )
        self.loading = False

    def action_refresh(self) -> None:
        self._refresh()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_toggle(self) -> None:
        tbl = self.query_one("#pmcp-table", DataTable)
        status_label = self.query_one("#pmcp-status", Static)
        if tbl.cursor_row is None or tbl.row_count == 0:
            return
        row_key = tbl.coordinate_to_cell_key((tbl.cursor_row, 0)).row_key.value
        if not row_key:
            return
        name = row_key
        agg = enumerate_mcp_servers()
        info = agg.get(name)
        if not info:
            status_label.update(f"[red]Not found: {name}[/red]")
            return
        if info["is_plugin"]:
            status_label.update(
                "[yellow]Plugin servers are managed via /plugin — not from here.[/yellow]"
            )
            return
        if name in read_project_mcp(self._target_dir):
            ok, msg = remove_from_project_mcp(name, self._target_dir)
        else:
            tmpl = (info.get("definitions") or {}).get("template")
            if not tmpl:
                tmpl = (info.get("definitions") or {}).get("project")
            ok, msg = add_template_to_project_mcp(name, tmpl, self._target_dir)
        status_label.update(
            f"[{'green' if ok else 'red'}]{'✓ ' if ok else '✗ '}{msg}[/]"
        )
        if self._on_change:
            self._on_change(len(read_project_mcp(self._target_dir)))
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "pmcp-back":
            self.action_back()
        elif bid == "pmcp-refresh":
            self.action_refresh()
        elif bid == "pmcp-toggle":
            self.action_toggle()
