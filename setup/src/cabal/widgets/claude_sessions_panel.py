# -*- coding: utf-8 -*-
"""ClaudeSessionsPanel — home-screen widget showing Claude Code sessions for the selected project."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, DataTable, Static

_PROJECTS_DIR = Path.home() / ".claude" / "projects"


class ClaudeSessionsPanel(Widget):
    """Compact session list for the currently selected project, loaded in a background thread."""

    DEFAULT_CSS = """
    ClaudeSessionsPanel {
        height: auto;
        padding: 1 2;
        margin: 0 2;
        background: $boost;
        border: round #CC006B;
    }
    ClaudeSessionsPanel #csp-titlebar { height: 3; align-vertical: middle; }
    ClaudeSessionsPanel #csp-title { content-align: left middle; height: auto; width: 1fr; }
    ClaudeSessionsPanel #csp-view-all { min-width: 16; height: 3; margin: 0; }
    ClaudeSessionsPanel DataTable { height: auto; max-height: 14; }
    ClaudeSessionsPanel #csp-status { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="csp-titlebar"):
            yield Static(
                "[bold bright_magenta]✦ Claude Sessions[/bold bright_magenta]",
                id="csp-title",
            )
            yield Button("View all sessions", id="csp-view-all", variant="primary")
        yield Static("[dim]Loading…[/dim]", id="csp-status")
        tbl = DataTable(id="csp-table", cursor_type="row")
        tbl.add_columns("Date", "Branch", "Duration", "Cost", "Tools", "Agents")
        yield tbl

    def on_mount(self) -> None:
        self.border_title = "Claude Sessions"
        self.refresh_sessions()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "csp-view-all":
            event.stop()
            from cabal.views.sessions import SessionsScreen
            self.app.push_screen(SessionsScreen())

    def refresh_sessions(self) -> None:
        project = self._current_project()
        if project is None:
            self._paint_no_project()
            return
        self.run_worker(
            self._load_sessions, thread=True, exclusive=True, group="csp-load"
        )

    def _current_project(self) -> Path | None:
        selected = getattr(self.app, "selected_project", None)
        return Path(selected) if selected else None

    def _load_sessions(self) -> None:
        from cabal.models.session import SessionSummary
        from cabal.session_pricing import load_pricing
        from cabal.session_reader import (
            compute_summary,
            infer_session_tree,
            read_session,
            scan_projects_dir,
        )

        project = self._current_project()
        if project is None:
            self.app.call_from_thread(self._paint_no_project)
            return

        all_sessions = scan_projects_dir(_PROJECTS_DIR)
        project_posix = project.as_posix().lower()
        matched = [
            s for s in all_sessions
            if Path(s.project_path).as_posix().lower() == project_posix
        ]

        if not matched:
            self.app.call_from_thread(self._paint_empty, str(project))
            return

        pricing = load_pricing()
        summaries: list[SessionSummary] = []
        for sess in matched:
            entries = read_session(sess)
            summaries.append(compute_summary(sess, entries, pricing))
        infer_session_tree(summaries)

        self.app.call_from_thread(self._paint_sessions, summaries)

    def _paint_no_project(self) -> None:
        self.query_one("#csp-status", Static).update(
            "[dim]No project selected — choose a project directory first.[/dim]"
        )
        self.query_one("#csp-table", DataTable).clear()

    def _paint_empty(self, project_str: str) -> None:
        self.query_one("#csp-status", Static).update(
            f"[dim]No sessions found for [italic]{project_str}[/italic].[/dim]"
        )
        self.query_one("#csp-table", DataTable).clear()

    def _paint_sessions(self, summaries: list) -> None:
        summaries.sort(
            key=lambda s: s.start_time or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        tbl = self.query_one("#csp-table", DataTable)
        tbl.clear()

        for s in summaries[:20]:
            date_str = s.start_time.strftime("%m-%d %H:%M") if s.start_time else "—"
            dur_s = s.duration_seconds
            if dur_s >= 3600:
                dur = f"{dur_s / 3600:.1f}h"
            elif dur_s >= 60:
                dur = f"{dur_s / 60:.0f}m"
            else:
                dur = f"{dur_s:.0f}s"
            prefix = "↳ " if s.parent_session_id else ""
            tbl.add_row(
                f"{prefix}{date_str}",
                (s.git_branch or "—")[:16],
                dur,
                f"${s.estimated_cost_usd:.3f}",
                str(len(s.tool_calls)),
                str(s.agent_count),
                key=s.session_id,
            )

        total_cost = sum(s.estimated_cost_usd for s in summaries)
        n = len(summaries)
        shown = min(n, 20)
        suffix = f" (showing {shown})" if n > 20 else ""
        self.query_one("#csp-status", Static).update(
            Text.from_markup(
                f"[dim]{n} session{'s' if n != 1 else ''}{suffix}"
                f"  ·  total [bold]${total_cost:.3f}[/bold][/dim]"
            )
        )
