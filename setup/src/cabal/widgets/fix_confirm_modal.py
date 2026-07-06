# -*- coding: utf-8 -*-
"""FixConfirmModal — per-finding confirmation before Package Security Check runs a fix."""

from __future__ import annotations

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from cabal.package_security.models import Finding


class FixConfirmModal(ModalScreen[bool]):
    """Show package, current -> target version, and the exact fix command. Dismisses with bool."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    FixConfirmModal { align: center middle; }
    FixConfirmModal #fcm-box {
        width: 76;
        height: auto;
        background: $surface;
        border: round $warning;
        padding: 1 2;
    }
    FixConfirmModal #fcm-title { text-style: bold; color: $warning; margin: 0 0 1 0; }
    FixConfirmModal #fcm-command { margin: 1 0; }
    FixConfirmModal .fcm-btn { width: 1fr; margin: 0 1 0 0; }
    FixConfirmModal #fcm-buttons { height: auto; }
    """

    def __init__(self, finding: Finding) -> None:
        super().__init__()
        self._finding = finding

    def compose(self) -> ComposeResult:
        f = self._finding
        target = f.target_version or "?"
        with Vertical(id="fcm-box"):
            yield Static("Fix — Package Security Check", id="fcm-title")
            yield Static(
                f"[bold]{escape_markup(f.package)}[/bold]  "
                f"([dim]{escape_markup(f.ecosystem)} · {escape_markup(f.kind)}[/dim])\n"
                f"{escape_markup(f.current_version)} → [green]{escape_markup(target)}[/green]"
            )
            yield Static(
                f"[cyan]{escape_markup(f.fix_command or '')}[/cyan]",
                id="fcm-command",
            )
            with Vertical(id="fcm-buttons"):
                yield Button("Run this fix", id="fcm-confirm", variant="warning", classes="fcm-btn")
                yield Button("Cancel (Esc)", id="fcm-cancel", classes="fcm-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fcm-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)
