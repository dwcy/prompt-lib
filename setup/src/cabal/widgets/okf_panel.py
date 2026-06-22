"""Small OKF status panel for the Cabal home screen."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Static
from textual.widget import Widget


class OkfPanel(Widget):
    DEFAULT_CSS = """
    OkfPanel {
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(self._render_status(), id="okf-panel-body")

    def _render_status(self) -> str:
        bundle = Path.cwd() / "docs" / "okf" / "prompt-lib"
        if (bundle / "graph.json").exists():
            return "[bold]OKF[/bold]\n[green]Graph bundle present.[/green]"
        return "[bold]OKF[/bold]\n[dim]No generated graph bundle yet.[/dim]"
