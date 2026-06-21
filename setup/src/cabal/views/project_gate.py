# -*- coding: utf-8 -*-
"""ProjectGateScreen — strict startup chooser: Init or Open a project before the main view."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.banner import HexBanner, subtitle_bar
from cabal.recent_projects import load_recents, record_recent, remove_recent
from cabal.widgets.env_panel import EnvPanel


def _fmt_time(iso: str) -> str:
    """Render a stored ISO-8601 UTC stamp as local 'YYYY-MM-DD HH:MM'."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


class ProjectGateScreen(Screen):
    """First screen shown on launch. A project path must be chosen before Home opens."""

    BINDINGS = [
        Binding("ctrl+q", "app.quit", "Quit"),
    ]

    CSS = """
    ProjectGateScreen #gate-recents-section { height: auto; margin: 1 2; }
    ProjectGateScreen #gate-recents-title {
        text-style: bold;
        color: #5FAFFF;
        margin: 0 0 1 0;
    }
    ProjectGateScreen #gate-recents { height: auto; max-height: 16; }
    ProjectGateScreen #gate-recents-empty { color: $text-muted; }
    """

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll(id="gate-scroll"):
            yield HexBanner(id="banner", classes="centered", show_subtitle=False)
            yield subtitle_bar()
            yield EnvPanel(id="env-summary")
            yield Static(
                "[bold bright_magenta]Select a project[/bold bright_magenta]\n"
                "[dim]CABAL operates on one project at a time. Init a new project or open "
                "an existing one — Local MCP, Local Config and Git local scope all bind to it.[/dim]",
                classes="panel",
            )
            with Horizontal(classes="ops-row"):
                yield Button("Init new project", id="gate-init", variant="error")
                yield Button("Clone repo", id="gate-clone", variant="primary")
                yield Button("Open existing project", id="gate-open", variant="primary")
            with Vertical(id="gate-recents-section"):
                yield Static("✦ Recent projects", id="gate-recents-title")
                yield Static(
                    "[dim]No projects opened yet — init or open one and it will appear "
                    "here. Click a row to reopen it.[/dim]",
                    id="gate-recents-empty",
                )
                yield DataTable(id="gate-recents")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        table = self.query_one("#gate-recents", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Project", "Path", "Last opened", "Type")
        self._load_recents()
        self.query_one("#gate-init", Button).focus()

    def on_screen_resume(self) -> None:
        # Reload after returning from Home so freshly init/opened projects show.
        self._load_recents()
        self._refresh_env_panel()

    def _refresh_env_panel(self) -> None:
        try:
            self.query_one("#env-summary", EnvPanel).refresh_project()
        except Exception:
            pass
        if getattr(self.app, "env_needs_refresh", False):
            self.app.env_needs_refresh = False
            try:
                self.query_one("#env-summary", EnvPanel).refresh_env()
            except Exception:
                pass

    def _load_recents(self) -> None:
        table = self.query_one("#gate-recents", DataTable)
        table.clear()
        recents = load_recents()
        self.query_one("#gate-recents-empty", Static).display = not recents
        table.display = bool(recents)
        for r in recents:
            table.add_row(
                r.name, r.path, _fmt_time(r.last_opened), r.action, key=r.path
            )

    def action_readme(self) -> None:
        from cabal.views.readme import ReadmeScreen

        self.app.push_screen(ReadmeScreen())

    def action_init_project(self) -> None:
        from cabal.views.init_project import InitProjectScreen

        self.app.push_screen(
            InitProjectScreen(
                on_created=lambda p: self._after_project_chosen(p, "init")
            )
        )

    def action_clone_repo(self) -> None:
        from cabal.views.github_repos import GitHubReposScreen

        self.app.push_screen(GitHubReposScreen(on_clone_done=self._after_clone))

    def action_open_project(self) -> None:
        from cabal.views.folder_browser import FolderBrowserScreen

        self.app.push_screen(FolderBrowserScreen(Path.cwd()), self._after_folder_picked)

    def _after_folder_picked(self, path: Path | None) -> None:
        if path is None:
            return
        self.app.selected_project = path
        self._after_project_chosen(path, "open")

    def _after_project_chosen(self, path: Path, action: str) -> None:
        record_recent(path, action)
        self._enter_home()

    def _after_clone(self, path: Path) -> None:
        self.app.selected_project = path
        self._after_project_chosen(path, "clone")

    def _enter_home(self) -> None:
        from cabal.views.home import HomeScreen

        self.app.push_screen(HomeScreen())

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        path_str = event.row_key.value
        if not path_str:
            return
        path = Path(path_str)
        if not path.is_dir():
            self.notify(
                f"{path} no longer exists — removed from history",
                severity="warning",
                timeout=8,
            )
            remove_recent(path)
            self._load_recents()
            return
        self.app.selected_project = path
        self._after_project_chosen(path, "open")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "gate-init":
            self.action_init_project()
        elif bid == "gate-clone":
            self.action_clone_repo()
        elif bid == "gate-open":
            self.action_open_project()
        elif bid == "btn-op-tools":
            from cabal.views.tools import ToolsScreen

            self.app.push_screen(ToolsScreen())
        elif bid == "btn-env":
            from cabal.views.env import EnvScreen

            self.app.push_screen(EnvScreen())
        elif bid == "btn-github":
            from cabal.views.github_repos import GitHubReposScreen

            self.app.push_screen(GitHubReposScreen())
