# -*- coding: utf-8 -*-
"""OpenCode setup screen."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.installers.ai_clis import opencode_desktop_install, opencode_install
from cabal.opencode_setup.conversion import (
    OpenCodeAsset,
    apply_assets,
    build_global_plan,
    build_project_plan,
)
from cabal.opencode_setup.paths import OPENCODE_TARGET
from cabal.opencode_setup.status import OpenCodeStatus, opencode_status
from cabal.tool_catalog import clean_console_output, redact_secret_text
from cabal.widgets.file_viewer import FileViewerModal


class OpenCodeSetupScreen(Screen):
    """Preview and deploy OpenCode-compatible config, skills, and bridge tools."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("ctrl+g", "apply_global", "Apply global"),
        Binding("ctrl+p", "apply_project", "Apply project"),
        Binding("v", "view_file", "View"),
    ]

    CSS = """
    OpenCodeSetupScreen #opencode-actions { height: auto; }
    OpenCodeSetupScreen .opencode-spacer { width: 1fr; }
    OpenCodeSetupScreen #opencode-preview { max-height: 60; }
    """

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_cyan]OpenCode Setup[/bold bright_cyan]\n"
                "[dim]Install the OpenCode CLI or desktop app, deploy compatible "
                "prompt-lib assets, "
                "and wire Codex/Claude/Gemini/Antigravity bridge tools.[/dim]",
                classes="panel",
            )
            yield Static("", id="opencode-status", classes="panel")
            with Horizontal(id="opencode-actions"):
                yield Button("Install CLI", id="opencode-install-cli", variant="success")
                yield Button(
                    "Install Desktop App",
                    id="opencode-install-desktop",
                    variant="success",
                )
                yield Button("Apply Global", id="opencode-apply-global", variant="success")
                yield Button("Apply Project", id="opencode-apply-project", variant="primary")
                yield Button("View (v)", id="opencode-view")
                yield Static("", classes="opencode-spacer")
                yield Button("Refresh", id="opencode-refresh")
                yield Button("Back", id="opencode-back")
            yield Static("", id="opencode-summary")
            yield DataTable(id="opencode-preview")
            yield Static("", id="opencode-result", classes="panel")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._global_assets: list[OpenCodeAsset] = []
        self._project_assets: list[OpenCodeAsset] = []
        self._row_assets: dict[str, OpenCodeAsset] = {}
        table = self.query_one("#opencode-preview", DataTable)
        table.cursor_type = "row"
        table.add_columns("Scope", "Group", "Asset", "State")
        self._refresh()
        table.focus()

    @staticmethod
    def _state_cell(state: str) -> str:
        if state == "NEW":
            return "[green]NEW[/green]"
        if state == "CHANGED":
            return "[yellow]CHANGED[/yellow]"
        return "[dim]UNCHANGED[/dim]"

    @staticmethod
    def _status_chip(ok: bool, label: str) -> str:
        return f"{'[green]OK[/green]' if ok else '[red]--[/red]'} {label}"

    def _status_text(self, status: OpenCodeStatus) -> str:
        chips = [
            self._status_chip(status.cli, f"OpenCode CLI {status.summary}"),
            self._status_chip(
                status.desktop_app,
                f"Desktop app {status.desktop_summary}",
            ),
            self._status_chip(status.global_config, "global config"),
            self._status_chip(status.skills_dir, "skills"),
            self._status_chip(status.tools_dir, "tools"),
            self._status_chip(status.codex_cli, "Codex CLI"),
            self._status_chip(status.codex_mcp_configured, "Codex MCP"),
            self._status_chip(status.claude_cli, "Claude CLI"),
            self._status_chip(status.gemini_cli, "Gemini CLI"),
            self._status_chip(status.antigravity_cli, "Antigravity"),
        ]
        target = escape_markup(str(OPENCODE_TARGET))
        return f"[bold]Target:[/bold] {target}\n" + "   ".join(chips)

    def _refresh(self) -> None:
        status = opencode_status()
        self.query_one("#opencode-status", Static).update(self._status_text(status))
        self.query_one("#opencode-install-cli", Button).display = not status.cli
        self.query_one("#opencode-install-desktop", Button).display = not status.desktop_app
        project = self.app.project_path()
        self._global_assets = build_global_plan()
        self._project_assets = build_project_plan(project)
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#opencode-preview", DataTable)
        table.clear()
        self._row_assets = {}
        totals = {"NEW": 0, "CHANGED": 0, "UNCHANGED": 0}
        for scope, assets in (("global", self._global_assets), ("project", self._project_assets)):
            for idx, asset in enumerate(assets):
                row_key = f"{scope}::{idx}"
                self._row_assets[row_key] = asset
                totals[asset.state] = totals.get(asset.state, 0) + 1
                table.add_row(
                    scope,
                    asset.group,
                    asset.label,
                    self._state_cell(asset.state),
                    key=row_key,
                )
        self.query_one("#opencode-summary", Static).update(
            f"[bold]Preview:[/bold] {len(self._row_assets)} assets   "
            f"[green]NEW {totals['NEW']}[/green]   "
            f"[yellow]CHANGED {totals['CHANGED']}[/yellow]   "
            f"[dim]UNCHANGED {totals['UNCHANGED']}[/dim]"
        )

    def _apply(self, scope: str, assets: Iterable[OpenCodeAsset]) -> None:
        try:
            copied, skipped = apply_assets(assets)
        except Exception as exc:
            self.query_one("#opencode-result", Static).update(
                f"[red]{scope} apply failed:[/red] {escape_markup(str(exc))}"
            )
            return
        self.query_one("#opencode-result", Static).update(
            f"[green]OK[/green] {scope}: {copied} copied/merged, {skipped} unchanged. "
            "[bold]Restart OpenCode to reload config and tools.[/bold]"
        )
        self._refresh()

    def action_apply_global(self) -> None:
        self._apply("global", self._global_assets)

    def action_apply_project(self) -> None:
        project = self.app.project_path()
        if not project.exists() or not project.is_dir():
            self.query_one("#opencode-result", Static).update(
                f"[red]Project path is not a directory:[/red] {escape_markup(str(project))}"
            )
            return
        self._apply("project", self._project_assets)

    def action_refresh(self) -> None:
        self._refresh()

    def action_view_file(self) -> None:
        table = self.query_one("#opencode-preview", DataTable)
        if table.row_count == 0:
            return
        try:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return
        asset = self._row_assets.get(key or "")
        if asset is None:
            return
        compare = asset.target if asset.target.is_file() else None
        self.app.push_screen(
            FileViewerModal(
                asset.source,
                f"{asset.group}: {asset.label}",
                compare_path=compare,
            )
        )

    def _install_done(self, kind: str, button_id: str, ok: bool, msg: str) -> None:
        mark = "[green]OK[/green]" if ok else "[red]FAILED[/red]"
        clean = clean_console_output(redact_secret_text(msg))
        body = "\n[dim]" + escape_markup(clean) + "[/dim]" if clean else ""
        self.query_one("#opencode-result", Static).update(f"{mark} OpenCode {kind} install{body}")
        self.query_one(button_id, Button).disabled = False
        self._refresh()

    def _install_cli_worker(self) -> None:
        try:
            ok, msg = opencode_install()
        except Exception as exc:
            ok, msg = False, str(exc)
        self.app.call_from_thread(self._install_done, "CLI", "#opencode-install-cli", ok, msg)

    def _install_desktop_worker(self) -> None:
        try:
            ok, msg = opencode_desktop_install()
        except Exception as exc:
            ok, msg = False, str(exc)
        self.app.call_from_thread(
            self._install_done,
            "desktop app",
            "#opencode-install-desktop",
            ok,
            msg,
        )

    def _start_cli_install(self) -> None:
        button = self.query_one("#opencode-install-cli", Button)
        button.disabled = True
        self.query_one("#opencode-result", Static).update(
            "[yellow]Installing OpenCode CLI via npm...[/yellow]"
        )
        self.run_worker(self._install_cli_worker, thread=True, exclusive=False)

    def _start_desktop_install(self) -> None:
        button = self.query_one("#opencode-install-desktop", Button)
        button.disabled = True
        self.query_one("#opencode-result", Static).update(
            "[yellow]Installing OpenCode Desktop app...[/yellow]"
        )
        self.run_worker(self._install_desktop_worker, thread=True, exclusive=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "opencode-install-cli":
            self._start_cli_install()
        elif bid == "opencode-install-desktop":
            self._start_desktop_install()
        elif bid == "opencode-apply-global":
            self.action_apply_global()
        elif bid == "opencode-apply-project":
            self.action_apply_project()
        elif bid == "opencode-view":
            self.action_view_file()
        elif bid == "opencode-refresh":
            self.action_refresh()
        elif bid == "opencode-back":
            self.app.pop_screen()
