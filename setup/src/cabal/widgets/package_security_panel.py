# -*- coding: utf-8 -*-
"""PackageSecurityPanel — Home-screen summary; auto-scans the open project on mount."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cabal.package_security import service
from cabal.package_security.models import ScanOutcome

_SEVERITY_ORDER = {"critical": 0, "high": 1, "moderate": 2, "medium": 2, "low": 3, "info": 4}


def _worst_severity_style(outcomes: list[ScanOutcome]) -> str:
    severities = [
        f.severity.lower()
        for outcome in outcomes
        for f in outcome.findings
        if f.kind == "vulnerable"
    ]
    if not severities:
        return "green"
    worst = min(severities, key=lambda s: _SEVERITY_ORDER.get(s, 4))
    return "red" if worst in {"critical", "high"} else "yellow"


def summarize(outcomes: list[ScanOutcome]) -> str:
    """Render a one/two-line summary of scan outcomes for the Home panel."""
    if not outcomes:
        return "[dim]No .NET, npm, or Python dependency files detected in this project.[/dim]"

    counts = {"vulnerable": 0, "outdated": 0, "deprecated": 0}
    notices: list[str] = []
    for outcome in outcomes:
        for f in outcome.findings:
            counts[f.kind] += 1
        notices.extend(outcome.notices)

    total = sum(counts.values())
    if total == 0 and not notices:
        return "[green]✓ No package security findings[/green]"

    style = _worst_severity_style(outcomes)
    parts = [f"{counts['vulnerable']} vulnerable", f"{counts['outdated']} outdated", f"{counts['deprecated']} deprecated"]
    line = f"[{style}]{' · '.join(parts)}[/{style}]"
    if notices:
        line += f"\n[yellow]⚑ {len(notices)} notice(s) — see Package Security Check[/yellow]"
    return line


class PackageSecurityPanel(Widget):
    """Async dependency-security summary — vulnerable/outdated/deprecated counts per project."""

    DEFAULT_CSS = """
    PackageSecurityPanel { height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Static("[dim]Scanning dependencies…[/dim]", id="pkgsec-summary")

    def on_mount(self) -> None:
        project = self.app.project_path()
        cached = service.load_cached(project)
        if cached is not None:
            self._apply(cached)
        self.run_worker(lambda: self._scan(project), thread=True, exclusive=True)

    def _scan(self, project) -> None:
        outcomes = service.scan_project(project)
        service.save_cache(project, outcomes)
        self.app.call_from_thread(self._apply, outcomes)

    def _apply(self, outcomes: list[ScanOutcome]) -> None:
        try:
            self.query_one("#pkgsec-summary", Static).update(summarize(outcomes))
        except Exception:
            pass
