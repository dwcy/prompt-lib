# -*- coding: utf-8 -*-
"""DashboardPanel — home-screen widget that renders a per-project dashboard snapshot.

Framework + rendering only: cache-first paint, per-section worker dispatch, and pure
section-to-Text rendering. No subprocess/network here — collectors live in services.
"""

from __future__ import annotations

import hashlib
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Static

from cabal.models.dashboard import (
    AvailabilityState,
    DashboardSnapshot,
    GitHubSection,
    GitSection,
    SupabaseSection,
    VercelSection,
)
from cabal.widget_cache import load_entry, save_entry

SECTIONS = ("git", "github", "supabase", "vercel")
CACHE_PREFIX = "dashboard:"

_SECTION_TITLES = {
    "git": "Git",
    "github": "GitHub",
    "supabase": "Supabase",
    "vercel": "Vercel",
}
_PLACEHOLDER = "[dim]select a project to see its dashboard[/dim]"
_REFRESHING = "[dim]refreshing…[/dim]"
_LOADING = "[dim]loading…[/dim]"

_STATE_HINTS = {
    AvailabilityState.NO_CLI: "required CLI not found on PATH",
    AvailabilityState.NOT_LINKED: "not linked",
    AvailabilityState.NOT_AUTHED: "not authenticated",
    AvailabilityState.TIMEOUT: "timed out",
    AvailabilityState.ERROR: "error",
}


class DashboardPanel(Widget):
    """Per-project dashboard: cache-first paint, threaded section workers, pure rendering."""

    DEFAULT_CSS = """
    DashboardPanel {
        height: auto;
        padding: 1 2;
        margin: 0 2;
        background: $boost;
        border: round $primary;
    }
    DashboardPanel #dash-titlebar { height: 3; align-vertical: middle; }
    DashboardPanel #dash-title { content-align: left middle; height: auto; width: 1fr; }
    DashboardPanel #dash-refresh { min-width: 14; height: 3; margin: 0; }
    DashboardPanel .dash-section-title { height: auto; margin: 1 0 0 0; }
    DashboardPanel .dash-section-body { height: auto; padding: 0 0 0 2; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._snapshot: DashboardSnapshot | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="dash-titlebar"):
            yield Static(
                "[bold bright_magenta]✦ Project dashboard[/bold bright_magenta]",
                id="dash-title",
            )
            yield Button("⟳  Refresh", id="dash-refresh", variant="primary")
        for name in SECTIONS:
            yield Static(
                f"[bold]{_SECTION_TITLES[name]}[/bold]",
                classes="dash-section-title",
            )
            yield Static(_LOADING, id=f"dash-{name}", classes="dash-section-body")

    def on_mount(self) -> None:
        project = self._resolve_project()
        if project is None:
            self._paint_placeholder()
            return
        cached = load_entry(self._cache_key(project))
        if cached is not None:
            restored = DashboardSnapshot.from_cached(cached)
            if restored is not None:
                self._snapshot = restored
                self._paint_all()
        self.refresh_dashboard()

    def refresh_dashboard(self) -> None:
        project = self._resolve_project()
        if project is None:
            self._paint_placeholder()
            return
        for name in SECTIONS:
            fetcher = getattr(self, f"_fetch_{name}", None)
            if callable(fetcher):
                self.query_one(f"#dash-{name}", Static).update(
                    Text.from_markup(_REFRESHING)
                )
                self.run_worker(fetcher, thread=True, exclusive=True, group=name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dash-refresh":
            event.stop()
            self.refresh_dashboard()

    def action_open_url(self, url: str) -> None:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _fetch_git(self) -> None:
        project = self._resolve_project()
        if project is None:
            return
        from cabal.dashboard_git_service import collect_git

        section = collect_git(project)
        self.app.call_from_thread(self._apply_section, "git", section)

    def _apply_section(self, name: str, section) -> None:
        if self._snapshot is None:
            self._snapshot = self._default_snapshot()
        setattr(self._snapshot, name, section)
        self.query_one(f"#dash-{name}", Static).update(
            self._section_text(name, section)
        )
        project = self._resolve_project()
        if project is not None:
            save_entry(self._cache_key(project), self._snapshot.to_cacheable())

    def _resolve_project(self) -> Path | None:
        selected = getattr(self.app, "selected_project", None)
        if selected is not None:
            return Path(selected)
        return None

    def _cache_key(self, project: Path) -> str:
        digest = hashlib.sha1(str(project).encode("utf-8")).hexdigest()[:16]
        return f"{CACHE_PREFIX}{digest}"

    def _default_snapshot(self) -> DashboardSnapshot:
        project = self._resolve_project()
        return DashboardSnapshot(
            project_path=str(project) if project is not None else "",
            captured_at=datetime.now(timezone.utc).isoformat(),
            git=GitSection(state=AvailabilityState.ERROR),
            github=GitHubSection(state=AvailabilityState.ERROR),
            supabase=SupabaseSection(state=AvailabilityState.ERROR),
            vercel=VercelSection(state=AvailabilityState.ERROR),
        )

    def _paint_placeholder(self) -> None:
        for name in SECTIONS:
            self.query_one(f"#dash-{name}", Static).update(
                Text.from_markup(_PLACEHOLDER)
            )

    def _paint_all(self) -> None:
        if self._snapshot is None:
            return
        for name in SECTIONS:
            section = getattr(self._snapshot, name, None)
            self.query_one(f"#dash-{name}", Static).update(
                self._section_text(name, section)
            )

    def _section_text(self, name: str, section) -> Text:
        if section is None:
            return Text.from_markup(_LOADING)
        builders = {
            "git": self._build_git_text,
            "github": self._build_github_text,
            "supabase": self._build_supabase_text,
            "vercel": self._build_vercel_text,
        }
        return builders[name](section)

    def _link_lines(self, label: str, url: str | None) -> list[str]:
        if not url:
            return []
        return [
            f"[bold]{label}:[/bold] [@click=open_url('{url}')]open[/]",
            f"  [dim]{url}[/dim]",
        ]

    def _state_hint(self, section) -> list[str]:
        hint = getattr(section, "hint", None) or _STATE_HINTS.get(
            section.state, "unavailable"
        )
        return [f"[dim]{hint}[/dim]"]

    def _enrich_lines(self, section) -> list[str]:
        enrich_state = getattr(section, "enrich_state", None)
        if enrich_state in (
            AvailabilityState.TOKEN_MISSING,
            AvailabilityState.TOKEN_REJECTED,
        ):
            hint = section.enrich_hint or (
                "token rejected"
                if enrich_state == AvailabilityState.TOKEN_REJECTED
                else "set a token for account-level fields"
            )
            return [f"[dim]{hint}[/dim]"]
        return []

    def _build_git_text(self, section: GitSection) -> Text:
        if section.state != AvailabilityState.OK:
            return Text.from_markup("\n".join(self._state_hint(section)))
        lines: list[str] = []
        if section.current_branch:
            label = "detached at" if section.detached else "branch"
            lines.append(f"[bold]{label}:[/bold] {section.current_branch}")
        if section.local_branches:
            lines.append(f"[bold]local branches:[/bold] {len(section.local_branches)}")
        for remote in section.remotes:
            tag = " [green](github)[/green]" if remote.is_github else ""
            lines.append(f"[bold]{remote.name}:[/bold] {remote.url}{tag}")
        return Text.from_markup("\n".join(lines) or _LOADING)

    def _build_github_text(self, section: GitHubSection) -> Text:
        if section.state != AvailabilityState.OK:
            return Text.from_markup("\n".join(self._state_hint(section)))
        lines: list[str] = []
        if section.owner_repo:
            via = (
                f" [dim](via {section.remote_used})[/dim]"
                if section.remote_used
                else ""
            )
            lines.append(f"[bold]repo:[/bold] {section.owner_repo}{via}")
        if section.runs:
            lines.append("[bold]workflow runs:[/bold]")
            for run in section.runs:
                outcome = run.conclusion or run.status
                lines.append(f"  {run.name} — {outcome} ({run.branch})")
                lines.extend(self._link_lines("  run", run.url))
        else:
            lines.append("[dim]no workflow runs[/dim]")
        if section.pull_requests:
            lines.append("[bold]open PRs:[/bold]")
            for pr in section.pull_requests:
                lines.append(f"  #{pr.number} {pr.title} — @{pr.author}")
                lines.extend(self._link_lines("  PR", pr.url))
        return Text.from_markup("\n".join(lines) or _LOADING)

    def _build_supabase_text(self, section: SupabaseSection) -> Text:
        if section.state != AvailabilityState.OK:
            lines = self._state_hint(section)
            lines.extend(self._link_lines("dashboard", section.dashboard_url))
            return Text.from_markup("\n".join(lines))
        lines = []
        if section.project_ref:
            lines.append(f"[bold]ref:[/bold] {section.project_ref}")
        for label, value in (
            ("status", section.status),
            ("region", section.region),
            ("plan", section.plan_name),
            ("db location", section.db_location),
            ("last migration", section.last_migration),
            ("last backup", section.last_backup),
        ):
            if value:
                lines.append(f"[bold]{label}:[/bold] {value}")
        for member in section.members:
            role = f" — {member.role}" if member.role else ""
            lines.append(f"  [dim]member:[/dim] {member.name}{role}")
        lines.extend(self._link_lines("dashboard", section.dashboard_url))
        lines.extend(
            self._link_lines("schema visualizer", section.schema_visualizer_url)
        )
        lines.extend(self._enrich_lines(section))
        return Text.from_markup("\n".join(lines) or _LOADING)

    def _build_vercel_text(self, section: VercelSection) -> Text:
        if section.state != AvailabilityState.OK:
            lines = self._state_hint(section)
            lines.extend(self._link_lines("dashboard", section.dashboard_url))
            return Text.from_markup("\n".join(lines))
        lines = []
        if section.project_name:
            lines.append(f"[bold]project:[/bold] {section.project_name}")
        for label, value in (
            ("deployment", section.latest_deployment_status),
            ("team / plan", section.team_plan),
            ("region", section.region),
        ):
            if value:
                lines.append(f"[bold]{label}:[/bold] {value}")
        for member in section.members:
            role = f" — {member.role}" if member.role else ""
            lines.append(f"  [dim]member:[/dim] {member.name}{role}")
        lines.extend(self._link_lines("dashboard", section.dashboard_url))
        lines.extend(
            self._link_lines("latest deployment", section.latest_deployment_url)
        )
        lines.extend(self._enrich_lines(section))
        return Text.from_markup("\n".join(lines) or _LOADING)
