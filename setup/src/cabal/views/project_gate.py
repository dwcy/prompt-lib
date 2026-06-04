# -*- coding: utf-8 -*-
"""ProjectGateScreen — strict startup chooser: Init or Open a project before the main view."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.banner import HexBanner


class ProjectGateScreen(Screen):
    """First screen shown on launch. A project path must be chosen before Home opens."""

    BINDINGS = [
        Binding("i", "init_project", "Init"),
        Binding("o", "open_project", "Open"),
        Binding("ctrl+q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll(id="gate-scroll"):
            yield HexBanner(id="banner", classes="centered")
            yield Static(
                "[bold bright_magenta]Select a project[/bold bright_magenta]\n"
                "[dim]CABAL operates on one project at a time. Init a new project or open "
                "an existing one — Local MCP, Local Config and Git local scope all bind to it.[/dim]",
                classes="panel",
            )
            with Horizontal(classes="ops-row"):
                yield Button("[I] Init new project", id="gate-init", variant="primary")
                yield Button(
                    "[O] Open existing project", id="gate-open", variant="primary"
                )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#gate-init", Button).focus()

    def action_init_project(self) -> None:
        from cabal.views.init_project import InitProjectScreen

        self.app.push_screen(
            InitProjectScreen(on_created=lambda _p: self._enter_home())
        )

    def action_open_project(self) -> None:
        from cabal.views.folder_browser import FolderBrowserScreen

        self.app.push_screen(FolderBrowserScreen(Path.cwd()), self._after_folder_picked)

    def _after_folder_picked(self, path: Path | None) -> None:
        if path is None:
            return
        self.app.selected_project = path
        self._enter_home()

    def _enter_home(self) -> None:
        from cabal.views.home import HomeScreen

        self.app.push_screen(HomeScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "gate-init":
            self.action_init_project()
        elif bid == "gate-open":
            self.action_open_project()
