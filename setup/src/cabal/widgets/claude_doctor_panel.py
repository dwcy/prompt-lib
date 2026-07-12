# -*- coding: utf-8 -*-
"""ClaudeDoctorPanel — Home-screen widget; auto-runs config + manifest health checks against ~/.claude on mount."""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Button, Static

from cabal._paths import TARGET
from cabal.apply_service import ApplyOutcome, outcome_summary
from cabal.config_doctor import Finding, finding_order, run_doctor_cached
from cabal.manifest_doctor import FILE_REPAIR_CATEGORIES, manifest_report
from cabal.repair_service import repair

_MAX_SHOWN = 10
_SEVERITY_MARK = {"error": ("✗", "red"), "warning": ("⚠", "yellow")}


def build_summary(findings: list[Finding], target: Path) -> str:
    """Render doctor findings as Rich markup for the Home panel."""
    header = f"[bold]Claude Doctor[/bold] [dim]({escape_markup(str(target))})[/dim]"
    if not findings:
        return f"{header}\n[green]✓ Claude is healthy :D[/green]"

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = len(findings) - errors
    counts: list[str] = []
    if errors:
        counts.append(f"[red]✗ {errors} error(s)[/red]")
    if warnings:
        counts.append(f"[yellow]⚠ {warnings} warning(s)[/yellow]")
    lines = [header, " · ".join(counts)]

    for f in findings[:_MAX_SHOWN]:
        mark, style = _SEVERITY_MARK.get(f.severity, ("•", "white"))
        lines.append(f"[{style}]{mark}[/{style}] [bold]{escape_markup(f.path)}[/bold]")
        lines.append(f"   {escape_markup(f.message)}")
        lines.append(f"   [dim]→ {escape_markup(f.hint)}[/dim]")
    if len(findings) > _MAX_SHOWN:
        lines.append(f"[dim]… and {len(findings) - _MAX_SHOWN} more[/dim]")
    return "\n".join(lines)


class ClaudeDoctorPanel(Widget):
    """Async config + manifest health summary with a targeted-repair action.

    Repair only ever re-deploys files doctor classified missing or stale —
    user-modified files are structurally excluded by ``repair_plan()``, so a
    per-file confirmation gate would confirm nothing; they are listed as
    skipped with a resolve-by-hand note instead (T017 documented choice).
    """

    DEFAULT_CSS = """
    ClaudeDoctorPanel { height: auto; margin: 1 0 0 0; }
    ClaudeDoctorPanel #claude-doctor-repair { margin: 1 0 0 0; }
    """

    def __init__(self, *, target: Path = TARGET, **kwargs) -> None:
        super().__init__(**kwargs)
        self._target = target
        self._findings: list[Finding] = []

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]Claude Doctor[/bold]\n[dim]Checking ~/.claude health…[/dim]",
            id="claude-doctor-summary",
        )
        yield Button(
            "Repair managed files", id="claude-doctor-repair", variant="warning"
        )

    def on_mount(self) -> None:
        self.query_one("#claude-doctor-repair", Button).display = False
        self.refresh_doctor()

    def refresh_doctor(self) -> None:
        self.run_worker(self._run_checks, thread=True, exclusive=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "claude-doctor-repair":
            return
        event.stop()
        event.button.disabled = True
        self.run_worker(self._repair_managed_files, thread=True, exclusive=True)

    def _run_checks(self) -> None:
        try:
            project_path = getattr(self.app, "project_path", None)
            project = project_path() if callable(project_path) else None
            config_findings, _ = run_doctor_cached(self._target, project=project)
            findings = [*config_findings, *manifest_report().findings]
            findings.sort(key=finding_order)
        except Exception as exc:  # never let a doctor bug take down Home
            self.app.call_from_thread(self._apply_error, exc)
            return
        self.app.call_from_thread(self._apply_findings, findings)

    def _repair_managed_files(self) -> None:
        try:
            outcome = repair()
        except Exception as exc:  # repair failure must not take down Home
            self.app.call_from_thread(self._show_repair_error, exc)
            return
        self.app.call_from_thread(self._show_repair_outcome, outcome)

    def _apply_findings(self, findings: list[Finding]) -> None:
        self._findings = findings
        try:
            self.query_one("#claude-doctor-summary", Static).update(
                build_summary(findings, self._target)
            )
            button = self.query_one("#claude-doctor-repair", Button)
            button.display = any(
                f.category in FILE_REPAIR_CATEGORIES for f in findings
            )
            button.disabled = False
        except Exception:
            pass

    def _apply_error(self, exc: Exception) -> None:
        try:
            self.query_one("#claude-doctor-summary", Static).update(
                "[bold]Claude Doctor[/bold]\n"
                f"[yellow]⚠ Doctor could not complete: {escape_markup(str(exc))}[/yellow]"
            )
        except Exception:
            pass

    def _show_repair_outcome(self, outcome: ApplyOutcome) -> None:
        lines = outcome_summary(outcome)
        skipped = [f.path for f in self._findings if f.category == "user-modified"]
        if skipped:
            lines.append(
                "Skipped user-modified (resolve by hand): " + ", ".join(skipped)
            )
        self.notify("\n".join(lines), title="Repair", timeout=10)
        self.refresh_doctor()

    def _show_repair_error(self, exc: Exception) -> None:
        self.notify(str(exc), title="Repair failed", severity="error", timeout=10)
        try:
            self.query_one("#claude-doctor-repair", Button).disabled = False
        except Exception:
            pass
