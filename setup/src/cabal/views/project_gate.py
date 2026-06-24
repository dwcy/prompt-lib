# -*- coding: utf-8 -*-
"""ProjectGateScreen — strict startup chooser: Init or Open a project before the main view."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Size
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.recent_projects import load_recents, record_recent, remove_recent
from cabal.widgets.env_panel import EnvPanel
from cabal.widgets.logo import CabalLogo

_RECENTS_COLUMN_LABELS = ("Project", "Path", "Last opened")


def _fmt_time(iso: str, now: datetime | None = None) -> str:
    """Render a stored ISO-8601 UTC stamp as relative time, then date."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone()
    current = now or datetime.now(local_dt.tzinfo)
    if current.tzinfo is None:
        current = current.replace(tzinfo=local_dt.tzinfo)
    delta = current.astimezone(local_dt.tzinfo) - local_dt
    seconds = max(0, int(delta.total_seconds()))
    minutes = seconds // 60
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days <= 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return local_dt.strftime("%Y-%m-%d")


class ProjectGateScreen(Screen):
    """First screen shown on launch. A project path must be chosen before Home opens."""

    BINDINGS = [
        Binding("ctrl+q", "app.quit", "Quit"),
    ]

    _recent_rows: list[tuple[str, str, str]]

    CSS = """
    ProjectGateScreen #gate-select-panel {
        height: auto;
        border: round #CC006B;
    }
    ProjectGateScreen #gate-project-description {
        height: auto;
        margin: 0 0 1 0;
        padding: 0;
        color: $text-muted;
    }
    ProjectGateScreen #gate-actions {
        height: 5;
        align: center middle;
        margin: 0;
        padding: 0;
    }
    ProjectGateScreen #gate-actions Button { width: 1fr; }
    ProjectGateScreen #gate-clone,
    ProjectGateScreen #gate-clone:focus {
        background: #16A34A;
        border: none;
        border-top: tall #86EFAC;
        border-bottom: tall #166534;
        color: white;
    }
    ProjectGateScreen #gate-clone:hover {
        background: #15803D;
        border: none;
        border-top: tall #22C55E;
        border-bottom: tall #14532D;
        color: white;
    }
    ProjectGateScreen #gate-recents-panel {
        width: 1fr;
        height: auto;
        margin: 1 0 0 0;
        border: round #FF55A5;
    }
    ProjectGateScreen #gate-recents {
        width: 1fr;
        height: auto;
        max-height: 16;
        margin: 0;
    }
    ProjectGateScreen #gate-recents-empty { color: $text-muted; }
    """

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll(id="gate-scroll"):
            yield CabalLogo(id="banner", classes="centered")
            yield EnvPanel(id="env-summary")
            with Vertical(id="gate-select-panel", classes="panel"):
                yield Static(
                    "Create, clone, or open projects for managing agentic "
                    "development assets like agents, skills, hooks, and settings.",
                    id="gate-project-description",
                )
                with Horizontal(id="gate-actions"):
                    yield Button("Init new project", id="gate-init", variant="error")
                    yield Button("Clone repo", id="gate-clone")
                    yield Button(
                        "Open existing project",
                        id="gate-open",
                        variant="primary",
                    )
                with Vertical(id="gate-recents-panel", classes="panel"):
                    yield Static(
                        "[dim]No projects opened yet — init or open one and it will "
                        "appear here. Click a row to reopen it.[/dim]",
                        id="gate-recents-empty",
                    )
                    yield DataTable(id="gate-recents")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        table = self.query_one("#gate-recents", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(*_RECENTS_COLUMN_LABELS)
        self.query_one("#gate-select-panel", Vertical).border_title = (
            "[bold #FF85B3]Projects[/]"
        )
        self.query_one("#gate-recents-panel", Vertical).border_title = (
            "[bold #FF55A5]Recent Projects[/]"
        )
        self._load_recents()
        self._reset_start_viewport()

    def on_screen_resume(self) -> None:
        # Reload after returning from Home so freshly init/opened projects show.
        self._load_recents()
        self._refresh_env_panel()
        self._reset_start_viewport()

    def _reset_start_viewport(self) -> None:
        self.query_one("#gate-init", Button).focus(scroll_visible=False)
        self.call_after_refresh(self._scroll_start_to_top)

    def _scroll_start_to_top(self) -> None:
        self.query_one("#gate-scroll", VerticalScroll).scroll_home(
            animate=False,
            immediate=True,
        )

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

    def on_resize(self) -> None:
        self.call_after_refresh(self._fit_recents_table_columns)

    def _load_recents(self) -> None:
        table = self.query_one("#gate-recents", DataTable)
        table.clear()
        recents = load_recents()
        self._recent_rows = [
            (r.name, r.path, _fmt_time(r.last_opened)) for r in recents
        ]
        self.query_one("#gate-recents-empty", Static).display = not recents
        table.display = bool(recents)
        for r, row in zip(recents, self._recent_rows):
            table.add_row(*row, key=r.path)
        self.call_after_refresh(self._fit_recents_table_columns)

    def _fit_recents_table_columns(self) -> None:
        table = self.query_one("#gate-recents", DataTable)
        rows = getattr(self, "_recent_rows", [])
        if not table.display or not rows:
            return
        columns = list(table.ordered_columns)
        if len(columns) != len(_RECENTS_COLUMN_LABELS):
            return

        available_width = table.content_region.width or table.size.width
        if available_width <= 0:
            self.call_after_refresh(self._fit_recents_table_columns)
            return

        min_widths = [
            max(len(label), *(len(row[index]) for row in rows))
            for index, label in enumerate(_RECENTS_COLUMN_LABELS)
        ]
        content_width = max(
            len(columns),
            available_width - (2 * table.cell_padding * len(columns)),
        )
        if sum(min_widths) < content_width:
            min_widths[1] += content_width - sum(min_widths)

        for column, width in zip(columns, min_widths):
            column.auto_width = False
            column.width = width

        render_width = sum(column.get_render_width(table) for column in columns)
        table.virtual_size = Size(render_width, table.virtual_size.height)
        table._clear_caches()
        table.refresh()

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
