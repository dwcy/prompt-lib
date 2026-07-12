# -*- coding: utf-8 -*-
"""RecoveryModal — Resume / Roll back / Review offer for an interrupted apply."""

from __future__ import annotations

from typing import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from cabal import recovery_service
from cabal.apply_service import outcome_summary
from cabal.install_manifest import InstallManifest

RecoveryVerdict = str  # "resumed" | "rolled-back"


class RecoveryModal(ModalScreen[RecoveryVerdict | None]):
    """Ask how to handle an apply that died mid-write.

    Dismisses with "resumed" or "rolled-back" after the chosen recovery
    completes, or None for Review (keep the in_progress state, the user
    proceeds manually).
    """

    BINDINGS = [Binding("escape", "review", "Review later")]

    CSS = """
    RecoveryModal { align: center middle; }
    RecoveryModal #rcv-box {
        width: 72;
        height: auto;
        background: $surface;
        border: round $warning;
        padding: 1 2;
    }
    RecoveryModal #rcv-title { text-style: bold; color: $warning; margin: 0 0 1 0; }
    RecoveryModal #rcv-detail { margin: 0 0 1 0; }
    RecoveryModal #rcv-status { margin: 0 0 1 0; height: auto; }
    RecoveryModal .rcv-btn { width: 100%; margin: 0 0 1 0; }
    """

    def __init__(self, manifest: InstallManifest) -> None:
        super().__init__()
        self._manifest = manifest

    def compose(self) -> ComposeResult:
        m = self._manifest
        components = ", ".join(m.components) if m.components else "(none recorded)"
        with Vertical(id="rcv-box"):
            yield Static("Interrupted apply detected", id="rcv-title")
            yield Static(
                f"A previous apply (cabal {m.tool_version}, started {m.applied_at}) "
                f"never completed.\nComponents: {components}",
                id="rcv-detail",
            )
            yield Static("", id="rcv-status")
            yield Button(
                "Resume — re-apply (idempotent)",
                id="rcv-resume",
                variant="success",
                classes="rcv-btn",
            )
            yield Button(
                "Roll back — restore backups, undo the apply",
                id="rcv-rollback",
                variant="error",
                classes="rcv-btn",
            )
            yield Button(
                "Review — keep as-is, decide later (Esc)",
                id="rcv-review",
                classes="rcv-btn",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "rcv-review":
            self.dismiss(None)
        elif bid == "rcv-resume":
            self._start_recovery("resumed", self._resume_lines)
        elif bid == "rcv-rollback":
            self._start_recovery("rolled-back", self._rollback_lines)

    def action_review(self) -> None:
        self.dismiss(None)

    def _start_recovery(
        self, verdict: RecoveryVerdict, work: Callable[[], list[str]]
    ) -> None:
        for button in self.query(Button):
            button.disabled = True
        self.query_one("#rcv-status", Static).update("[dim]Working…[/dim]")

        def run() -> None:
            try:
                lines = work()
            except Exception as exc:
                self.app.call_from_thread(
                    self._show_result, f"[red]Recovery failed: {exc}[/red]", None
                )
                return
            self.app.call_from_thread(self._show_result, "\n".join(lines), verdict)

        self.run_worker(run, thread=True, exclusive=True)

    def _show_result(self, message: str, verdict: RecoveryVerdict | None) -> None:
        self.query_one("#rcv-status", Static).update(message)
        if verdict is None:
            for button in self.query(Button):
                button.disabled = False
            return
        self.app.notify(message, title="Recovery", timeout=8)
        self.dismiss(verdict)

    @staticmethod
    def _resume_lines() -> list[str]:
        return outcome_summary(recovery_service.resume_interrupted())

    @staticmethod
    def _rollback_lines() -> list[str]:
        return recovery_service.rollback_summary(
            recovery_service.rollback_interrupted()
        )


def push_recovery_if_interrupted(
    screen,
    on_done: Callable[[RecoveryVerdict | None], None] | None = None,
) -> bool:
    """Push RecoveryModal on the screen's app when an in_progress manifest exists.

    Returns True when the modal was raised — callers guarding an apply must
    then stop and wait for the user's choice.
    """
    manifest = recovery_service.interrupted_state()
    if manifest is None:
        return False
    screen.app.push_screen(RecoveryModal(manifest), on_done)
    return True
