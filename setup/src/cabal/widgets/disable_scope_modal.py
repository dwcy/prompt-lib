# -*- coding: utf-8 -*-
"""DisableScopeModal — pick which active scope to disable a multi-scope MCP server from."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

_SCOPE_LABELS = {
    "user": "Global (user — all projects)",
    "local": "Local (this project, ~/.claude.json)",
    "project": "Project (.mcp.json)",
}


class DisableScopeModal(ModalScreen[str | None]):
    """Ask which active scope to remove a server from. Dismisses with the scope or None."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    DisableScopeModal { align: center middle; }
    DisableScopeModal #dsm-box {
        width: 64;
        height: auto;
        background: $surface;
        border: round $error;
        padding: 1 2;
    }
    DisableScopeModal #dsm-title { text-style: bold; color: $error; margin: 0 0 1 0; }
    DisableScopeModal .dsm-btn { width: 100%; margin: 0 0 1 0; }
    """

    def __init__(self, name: str, scopes: list[str]) -> None:
        super().__init__()
        self._name = name
        self._scopes = scopes

    def compose(self) -> ComposeResult:
        with Vertical(id="dsm-box"):
            yield Static(
                f"Disable [b]{self._name}[/b] from which scope?", id="dsm-title"
            )
            for s in self._scopes:
                yield Button(
                    _SCOPE_LABELS.get(s, s),
                    id=f"dsm-{s}",
                    variant="error",
                    classes="dsm-btn",
                )
            yield Button("Cancel (Esc)", id="dsm-cancel", classes="dsm-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "dsm-cancel":
            self.dismiss(None)
        elif bid.startswith("dsm-"):
            self.dismiss(bid[len("dsm-") :])

    def action_cancel(self) -> None:
        self.dismiss(None)
