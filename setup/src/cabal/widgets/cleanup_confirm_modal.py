# -*- coding: utf-8 -*-
"""CleanupConfirmModal — shows the exact files to back up + delete before cleanup runs."""

from __future__ import annotations

from typing import Sequence

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from cabal.cleanup_service import ExtraFile


class CleanupConfirmModal(ModalScreen[bool]):
    """List every file to be backed up then deleted. Dismisses with a bool."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    CleanupConfirmModal { align: center middle; }
    CleanupConfirmModal #ccm-box {
        width: 84;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: round $warning;
        padding: 1 2;
    }
    CleanupConfirmModal #ccm-title { text-style: bold; color: $warning; margin: 0 0 1 0; }
    CleanupConfirmModal #ccm-files { height: auto; max-height: 20; margin: 1 0; }
    CleanupConfirmModal .ccm-btn { width: 1fr; margin: 0 1 0 0; }
    CleanupConfirmModal #ccm-buttons { height: auto; margin: 1 0 0 0; }
    """

    def __init__(self, extras: Sequence[ExtraFile]) -> None:
        super().__init__()
        self._extras = list(extras)

    def compose(self) -> ComposeResult:
        n = len(self._extras)
        with Vertical(id="ccm-box"):
            yield Static("Cleanup extras — backup then delete", id="ccm-title")
            yield Static(
                f"[bold]{n}[/bold] file(s) will be copied to a cleanup backup, "
                "verified, and then removed from [dim]~/.claude[/dim].\n"
                "[dim]Nothing is deleted until its backup is verified. "
                "You can restore any cleanup from this screen.[/dim]"
            )
            with VerticalScroll(id="ccm-files"):
                for ex in self._extras:
                    tag = (
                        "[green]stale[/green]"
                        if ex.classification == "stale"
                        else "[yellow]unknown[/yellow]"
                    )
                    yield Static(
                        f"  {tag}  [dim]{escape_markup(ex.component_label)}/[/dim]"
                        f"{escape_markup(ex.rel.as_posix())}"
                    )
            with Vertical(id="ccm-buttons"):
                yield Button(
                    "Back up + delete",
                    id="ccm-confirm",
                    variant="warning",
                    classes="ccm-btn",
                )
                yield Button("Cancel (Esc)", id="ccm-cancel", classes="ccm-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "ccm-confirm")

    def action_cancel(self) -> None:
        self.dismiss(False)
