# -*- coding: utf-8 -*-
"""ClaudeDoctorPanel — Home-screen widget; auto-runs config health checks against ~/.claude on mount."""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cabal._paths import TARGET
from cabal.config_doctor import Finding, run_doctor

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
    """Async config-health summary: healthy :D, or the unhealthy files with why + review hints."""

    DEFAULT_CSS = """
    ClaudeDoctorPanel { height: auto; margin: 1 0 0 0; }
    """

    def __init__(self, *, target: Path = TARGET, **kwargs) -> None:
        super().__init__(**kwargs)
        self._target = target

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]Claude Doctor[/bold]\n[dim]Checking ~/.claude health…[/dim]",
            id="claude-doctor-summary",
        )

    def on_mount(self) -> None:
        self.refresh_doctor()

    def refresh_doctor(self) -> None:
        self.run_worker(self._run_checks, thread=True, exclusive=True)

    def _run_checks(self) -> None:
        try:
            project_path = getattr(self.app, "project_path", None)
            project = project_path() if callable(project_path) else None
            findings = run_doctor(self._target, project=project)
        except Exception as exc:  # never let a doctor bug take down Home
            self.app.call_from_thread(self._apply_error, exc)
            return
        self.app.call_from_thread(self._apply_findings, findings)

    def _apply_findings(self, findings: list[Finding]) -> None:
        try:
            self.query_one("#claude-doctor-summary", Static).update(
                build_summary(findings, self._target)
            )
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
