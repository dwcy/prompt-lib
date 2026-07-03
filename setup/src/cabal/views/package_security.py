# -*- coding: utf-8 -*-
"""PackageSecurityScreen — "Package Security Check": scan + per-finding Fix confirmation."""

from __future__ import annotations

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.package_security import service
from cabal.package_security.models import Finding, ScanOutcome
from cabal.widgets.fix_confirm_modal import FixConfirmModal

_SEVERITY_STYLE = {
    "critical": "bold red",
    "high": "red",
    "moderate": "yellow",
    "medium": "yellow",
    "low": "dim",
    "info": "dim",
}


def _severity_markup(severity: str) -> str:
    style = _SEVERITY_STYLE.get(severity.lower(), "white")
    return f"[{style}]{escape_markup(severity)}[/{style}]"


class PackageSecurityScreen(Screen):
    """Full "Package Security Check" — findings table + one confirmation per Fix."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("f", "fix", "Fix"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._findings: dict[str, Finding] = {}

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Package Security Check ✦[/bold bright_magenta]\n"
                "[dim]Vulnerable, outdated, and deprecated packages across .NET, npm/frontend, "
                "and Python. Highlight a row and press Fix (f) — nothing is changed until you "
                "confirm the exact command.[/dim]",
                classes="panel",
            )
            yield Static("", id="pkgsec-notices", classes="panel")
            yield DataTable(id="pkgsec-table")
            with Horizontal():
                yield Button("Refresh", id="pkgsec-refresh")
                yield Button("Fix (f)", id="pkgsec-fix", variant="warning")
            yield Static("", id="pkgsec-status", classes="panel")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        table = self.query_one("#pkgsec-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Ecosystem", "Package", "Kind", "Severity", "Current → Target", "Fix")
        self._project = self.app.project_path()
        cached = service.load_cached(self._project)
        if cached is not None:
            self._apply_outcomes(cached)
        self.query_one("#pkgsec-status", Static).update("[dim]Scanning…[/dim]")
        self.run_worker(self._scan, thread=True, exclusive=True)

    def _scan(self) -> None:
        outcomes = service.scan_project(self._project)
        service.save_cache(self._project, outcomes)
        self.app.call_from_thread(self._apply_outcomes, outcomes)
        self.app.call_from_thread(
            self.query_one("#pkgsec-status", Static).update, "[green]✓ Scan complete[/green]"
        )

    def _apply_outcomes(self, outcomes: list[ScanOutcome]) -> None:
        table = self.query_one("#pkgsec-table", DataTable)
        table.clear()
        self._findings = {}
        notices: list[str] = []
        for outcome in outcomes:
            notices.extend(outcome.notices)
            for finding in outcome.findings:
                self._findings[finding.key] = finding
                target = finding.target_version or "?"
                fix_state = "[cyan]available[/cyan]" if finding.fix_command else "[dim]manual review[/dim]"
                table.add_row(
                    finding.ecosystem,
                    finding.package,
                    finding.kind,
                    _severity_markup(finding.severity),
                    f"{finding.current_version} → {target}",
                    fix_state,
                    key=finding.key,
                )
        notices_widget = self.query_one("#pkgsec-notices", Static)
        if notices:
            notices_widget.update(
                "\n".join(f"[yellow]⚑ {escape_markup(n)}[/yellow]" for n in notices)
            )
        else:
            notices_widget.update("")

    def _highlighted_finding(self) -> Finding | None:
        table = self.query_one("#pkgsec-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return None
        return self._findings.get(key or "")

    def action_fix(self) -> None:
        finding = self._highlighted_finding()
        if finding is None:
            return
        if not finding.fix_command:
            self.notify(
                "No automated fix available — review this finding manually.",
                title="Fix",
                severity="warning",
                timeout=6,
            )
            return
        self.app.push_screen(
            FixConfirmModal(finding), lambda confirmed: self._apply_fix_decision(finding, confirmed)
        )

    def _apply_fix_decision(self, finding: Finding, confirmed: bool | None) -> None:
        if not confirmed:
            return
        self.query_one("#pkgsec-status", Static).update(
            f"[cyan]Applying fix for {escape_markup(finding.package)}…[/cyan]"
        )
        self.run_worker(lambda: self._run_fix(finding), thread=True, exclusive=False)

    def _run_fix(self, finding: Finding) -> None:
        ok, message = service.apply_fix(finding, self._project)
        self.app.call_from_thread(self._after_fix, finding, ok, message)

    def _after_fix(self, finding: Finding, ok: bool, message: str) -> None:
        color = "green" if ok else "red"
        self.query_one("#pkgsec-status", Static).update(
            f"[{color}]{escape_markup(finding.package)}: {escape_markup(message)}[/{color}]"
        )
        self.notify(message, title=finding.package, severity="information" if ok else "error", timeout=10)
        if ok:
            self.action_refresh()

    def action_refresh(self) -> None:
        self.query_one("#pkgsec-status", Static).update("[dim]Scanning…[/dim]")
        self.run_worker(self._scan, thread=True, exclusive=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "pkgsec-refresh":
            self.action_refresh()
        elif bid == "pkgsec-fix":
            self.action_fix()
