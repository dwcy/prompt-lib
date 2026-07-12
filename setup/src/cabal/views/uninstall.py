# -*- coding: utf-8 -*-
"""UninstallScreen — preview, confirm, and report a manifest-driven uninstall.

View only: composes the preview table and handles events; all planning and
removal work runs in `cabal.uninstall_service` on a thread worker.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Footer, Static

from cabal._paths import TARGET
from cabal.app_widgets import AppHeader
from cabal.install_manifest import ManifestError
from cabal.uninstall_service import (
    InterruptedInstallError,
    NoManifestError,
    UninstallPlan,
    UninstallResult,
    uninstall,
    uninstall_plan,
    uninstall_summary,
)
from cabal.views.recovery_modal import push_recovery_if_interrupted

_RUN_LABEL = "Uninstall…"
_CONFIRM_LABEL = "Confirm uninstall"


class UninstallScreen(Screen):
    """Remove / keep / missing preview → explicit confirm → per-step report."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    CSS = """
    UninstallScreen #unst-actions { height: auto; }
    UninstallScreen .unst-spacer { width: 1fr; }
    UninstallScreen #unst-restore { margin: 0 1 0 0; }
    UninstallScreen #unst-table { max-height: 60; }
    """

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]Uninstall cabal-managed files[/bold bright_magenta]\n"
                f"[dim]Removes exactly what the install manifest records under {TARGET}, "
                "then the ~/.claude/.cabal state dir. User-modified and user-created "
                "files are kept.[/dim]",
                classes="panel",
            )
            with Horizontal(id="unst-actions"):
                yield Button(_RUN_LABEL, id="unst-run", variant="error")
                yield Button("Legacy scan", id="unst-legacy", variant="warning")
                yield Static("", classes="unst-spacer")
                yield Checkbox("Restore pre-install backups", id="unst-restore")
                yield Button("Refresh (Ctrl+R)", id="unst-refresh")
            yield Static("", id="unst-summary")
            yield DataTable(id="unst-table")
            yield Static("", id="unst-status", classes="panel")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._plan: UninstallPlan | None = None
        self._armed = False
        self._legacy = False
        table = self.query_one("#unst-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Plan", "Component", "File", "Note")
        self.query_one("#unst-legacy", Button).display = False
        try:
            if push_recovery_if_interrupted(self, lambda _v: self._load_plan()):
                return
        except ManifestError as exc:
            self._show_blocked(str(exc))
            return
        self._load_plan()

    def action_refresh(self) -> None:
        self._load_plan()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "unst-refresh":
            self._load_plan()
        elif bid == "unst-legacy":
            self._legacy = True
            self._load_plan()
        elif bid == "unst-run":
            self._confirm_or_run()

    # ── plan loading ────────────────────────────────────────────────────

    def _load_plan(self) -> None:
        self._disarm()
        self._plan = None
        self.query_one("#unst-run", Button).disabled = True
        self.query_one("#unst-status", Static).update("[dim]Scanning…[/dim]")
        legacy = self._legacy

        def work() -> None:
            try:
                plan = uninstall_plan(legacy=legacy)
            except NoManifestError as exc:
                self.app.call_from_thread(self._show_no_manifest, str(exc))
                return
            except (InterruptedInstallError, ManifestError) as exc:
                self.app.call_from_thread(self._show_blocked, str(exc))
                return
            self.app.call_from_thread(self._show_plan, plan)

        self.run_worker(work, thread=True, exclusive=True)

    def _show_plan(self, plan: UninstallPlan) -> None:
        self._plan = plan
        table = self.query_one("#unst-table", DataTable)
        table.clear()
        for item in plan.remove:
            table.add_row("[red]remove[/red]", item.component, item.rel, item.reason)
        for item in plan.skip:
            table.add_row("[yellow]keep[/yellow]", item.component, item.rel, item.reason)
        for item in plan.missing:
            table.add_row("[dim]missing[/dim]", item.component, item.rel, item.reason)
        mode = " [yellow](legacy scan — no manifest)[/yellow]" if plan.legacy else ""
        self.query_one("#unst-summary", Static).update(
            f"[bold red]{len(plan.remove)} to remove[/bold red]   "
            f"[yellow]{len(plan.skip)} kept[/yellow]   "
            f"[dim]{len(plan.missing)} already missing[/dim]   "
            f"{len(plan.backups)} backup file(s) restorable{mode}"
        )
        self.query_one("#unst-run", Button).disabled = False
        self.query_one("#unst-status", Static).update(
            "[dim]Review the plan, then press Uninstall. "
            "Kept rows are never deleted.[/dim]"
        )

    def _show_no_manifest(self, message: str) -> None:
        self.query_one("#unst-table", DataTable).clear()
        self.query_one("#unst-summary", Static).update("")
        self.query_one("#unst-legacy", Button).display = True
        self.query_one("#unst-status", Static).update(
            f"[yellow]{message}.[/yellow]\n"
            "[dim]Legacy scan lists registry files on disk instead — only files "
            "byte-matching the bundled source are removable.[/dim]"
        )

    def _show_blocked(self, message: str) -> None:
        self.query_one("#unst-table", DataTable).clear()
        self.query_one("#unst-summary", Static).update("")
        self.query_one("#unst-status", Static).update(f"[red]{message}[/red]")

    # ── confirm + execute ───────────────────────────────────────────────

    def _confirm_or_run(self) -> None:
        if self._plan is None:
            return
        if not self._armed:
            self._armed = True
            self.query_one("#unst-run", Button).label = _CONFIRM_LABEL
            restore = self.query_one("#unst-restore", Checkbox).value
            restore_note = (
                " and restores pre-install backups" if restore else ""
            )
            self.query_one("#unst-status", Static).update(
                f"[bold yellow]This removes {len(self._plan.remove)} file(s) plus "
                f"~/.claude/.cabal{restore_note}. "
                "Press again to confirm — Refresh cancels.[/bold yellow]"
            )
            return
        self._start_uninstall()

    def _disarm(self) -> None:
        self._armed = False
        try:
            self.query_one("#unst-run", Button).label = _RUN_LABEL
        except Exception:
            pass

    def _start_uninstall(self) -> None:
        plan = self._plan
        if plan is None:
            return
        restore = self.query_one("#unst-restore", Checkbox).value
        for button in self.query(Button):
            button.disabled = True
        self.query_one("#unst-status", Static).update("[dim]Removing…[/dim]")

        def work() -> None:
            try:
                result = uninstall(plan, restore_backups=restore)
            except Exception as exc:
                self.app.call_from_thread(self._show_failure, str(exc))
                return
            self.app.call_from_thread(self._show_result, result)

        self.run_worker(work, thread=True, exclusive=True)

    def _show_result(self, result: UninstallResult) -> None:
        self._plan = None
        self._disarm()
        lines = uninstall_summary(result)
        colour = "red" if result.errors else "green"
        self.query_one("#unst-status", Static).update(
            f"[bold {colour}]Uninstall finished.[/bold {colour}]\n" + "\n".join(lines)
        )
        self.query_one("#unst-refresh", Button).disabled = False
        self.query_one("#unst-legacy", Button).disabled = False
        self.notify("\n".join(lines), title="Uninstall", timeout=8)

    def _show_failure(self, message: str) -> None:
        self._disarm()
        for button in self.query(Button):
            button.disabled = False
        self.query_one("#unst-status", Static).update(
            f"[red]Uninstall failed: {message}[/red]\n"
            "[dim]The install manifest is kept while errors remain — re-run after "
            "resolving them.[/dim]"
        )
