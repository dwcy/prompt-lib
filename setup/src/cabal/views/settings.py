# -*- coding: utf-8 -*-
"""SettingsScreen — toggle Claude Code settings; global as baseline, writes go local."""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.claude_settings import (
    CATALOG,
    SettingDef,
    effective_value,
    global_value,
    read_global,
    read_local,
    reset_local,
    write_local,
)


class SettingsScreen(Screen):
    """Edit Claude settings: global values are the baseline; toggles override locally."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Claude Settings ✦[/bold bright_magenta]\n"
                "[dim]Global settings are the default. Toggling any setting writes it to this project's "
                ".claude/settings.local.json, which overrides the global value for this project.[/dim]\n"
                "[dim]● from global · ● local override · ○ available (not set globally).[/dim]",
                classes="panel",
            )
            yield Static("", id="set-project", classes="panel")
            for sd in CATALOG:
                yield Checkbox(sd.label, id=f"set-{sd.key}")
                yield Static("", id=f"meta-{sd.key}", classes="help-text")
            with Horizontal():
                yield Button("Reset local overrides", id="set-reset", variant="error")
                yield Button("Refresh (Ctrl+R)", id="set-refresh")
            yield Static("", id="set-status", classes="panel")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._refresh_rows()

    def _project(self) -> Path:
        return self.app.project_path()

    @staticmethod
    def _meta(sd: SettingDef, gl: dict, lo: dict) -> str:
        if sd.key in lo:
            src = f"[yellow]● local override[/yellow]  ·  global default: {'on' if global_value(sd, gl) else 'off'}"
        elif sd.key in gl:
            src = "[green]● from global[/green]"
        else:
            src = f"[dim]○ available — not set globally (default {'on' if sd.default else 'off'})[/dim]"
        return f"{sd.description}\n{src}"

    def _refresh_rows(self) -> None:
        gl = read_global()
        lo = read_local(self._project())
        self.query_one("#set-project", Static).update(
            f"[bold]Project:[/bold]  {escape_markup(str(self._project()))}"
        )
        for sd in CATALOG:
            cb = self.query_one(f"#set-{sd.key}", Checkbox)
            with cb.prevent(Checkbox.Changed):
                cb.value = effective_value(sd, gl, lo)
            self.query_one(f"#meta-{sd.key}", Static).update(self._meta(sd, gl, lo))

    def action_refresh(self) -> None:
        self._refresh_rows()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        cid = event.checkbox.id or ""
        key = cid[len("set-") :]
        sd = next((s for s in CATALOG if s.key == key), None)
        if sd is None:
            return
        target = write_local(self._project(), key, event.value)
        gl = read_global()
        lo = read_local(self._project())
        self.query_one(f"#meta-{key}", Static).update(self._meta(sd, gl, lo))
        self.query_one("#set-status", Static).update(
            f"[green]✓ {sd.label} = {str(event.value).lower()}[/green]  "
            f"[dim]→ {escape_markup(str(target))}[/dim]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "set-refresh":
            self._refresh_rows()
        elif bid == "set-reset":
            count = reset_local(self._project())
            self._refresh_rows()
            msg = (
                f"[green]✓ Removed {count} local override(s) — back to global defaults.[/green]"
                if count
                else "[dim]No local overrides to remove.[/dim]"
            )
            self.query_one("#set-status", Static).update(msg)
