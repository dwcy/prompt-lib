# -*- coding: utf-8 -*-
"""CleanupScreen — review, back up, and delete stale ~/.claude extras.

Lists target-only extras grouped by component with per-file toggles (stale checked
by default, unknown unchecked), confirms via CleanupConfirmModal, and runs the
backup-first removal. Restoring a cleanup lives in the sibling CleanupRestoreScreen.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from cabal._paths import TARGET
from cabal.app_widgets import AppHeader
from cabal.cleanup_service import (
    CleanupResult,
    ExtraFile,
    backup_and_remove,
    collect_extras,
    group_by_component,
)
from cabal.widgets.cleanup_confirm_modal import CleanupConfirmModal


class CleanupScreen(Screen):
    """Select stale extras under ~/.claude, back them up, and delete them."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "clean", "Clean up"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    CSS = """
    CleanupScreen #cln-actions { height: auto; }
    CleanupScreen .cln-spacer { width: 1fr; }
    CleanupScreen #cln-table { max-height: 60; }
    """

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]Cleanup extras[/bold bright_magenta]\n"
                f"[dim]Files in {TARGET} that are no longer in this repo.[/dim]\n"
                "[dim]Enter (or click) toggles a file · [green]stale[/green] rows are "
                "checked by default · [yellow]unknown[/yellow] rows may be user-authored "
                "(review first) · Clean up (Ctrl+A) backs up then deletes.[/dim]",
                classes="panel",
            )
            with Horizontal(id="cln-actions"):
                yield Button(
                    "Clean up selected (Ctrl+A)", id="cln-apply", variant="warning"
                )
                yield Static("", classes="cln-spacer")
                yield Button("Restore a cleanup", id="cln-restore", variant="primary")
            yield Static("", id="cln-summary")
            yield DataTable(id="cln-table")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._use: dict[str, bool] = {}
        self._by_key: dict[str, ExtraFile] = {}
        tbl = self.query_one("#cln-table", DataTable)
        tbl.cursor_type = "row"
        tbl.add_columns("Use", "File", "Why")
        self._reload()
        tbl.focus()

    @staticmethod
    def _row_key(ex: ExtraFile) -> str:
        return f"{ex.component_key}::{ex.rel.as_posix()}"

    @staticmethod
    def _box(symbol: str, color: str = "green") -> str:
        return rf"[{color}]\[{symbol}][/{color}]"

    def _reload(self) -> None:
        extras = collect_extras()
        seen = {self._row_key(ex) for ex in extras}
        self._by_key = {self._row_key(ex): ex for ex in extras}
        self._use = {
            k: (
                self._use[k]
                if k in self._use
                else self._by_key[k].classification == "stale"
            )
            for k in seen
        }
        self._refresh_table(group_by_component(extras))

    def _refresh_table(self, grouped: list[tuple[str, list[ExtraFile]]]) -> None:
        tbl = self.query_one("#cln-table", DataTable)
        tbl.clear()
        total = stale = unknown = 0
        if not grouped:
            tbl.add_row("", "[green]Nothing to clean up.[/green]", "", key="__empty__")
        for label, items in grouped:
            tbl.add_row(
                "", f"[bold]{label}[/bold] ({len(items)})", "", key=f"group::{label}"
            )
            for ex in items:
                total += 1
                key = self._row_key(ex)
                if ex.classification == "stale":
                    stale += 1
                    why = "[green]stale — safe to remove[/green]"
                else:
                    unknown += 1
                    why = "[yellow]unknown — may be user-authored[/yellow]"
                box = self._box("✓") if self._use.get(key) else self._box(" ")
                tbl.add_row(box, f"  └ {ex.rel.as_posix()}", why, key=key)
        selected = sum(1 for k, v in self._use.items() if v)
        self.query_one("#cln-summary", Static).update(
            f"[bold]Selected: {selected}[/bold]   "
            f"[dim]Extras: {total}[/dim]   "
            f"[green]stale {stale}[/green]   "
            f"[yellow]unknown {unknown}[/yellow]"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value or ""
        if key in self._by_key:
            self._use[key] = not self._use.get(key, False)
            self._reload()
            self.query_one("#cln-table", DataTable).move_cursor(row=event.cursor_row)

    def action_refresh(self) -> None:
        self._reload()

    def action_clean(self) -> None:
        chosen = [
            self._by_key[k] for k, v in self._use.items() if v and k in self._by_key
        ]
        if not chosen:
            self.notify("Nothing selected.", severity="warning", timeout=4)
            return
        chosen.sort(key=lambda e: (e.component_label, e.rel.as_posix()))
        self.app.push_screen(CleanupConfirmModal(chosen), self._after_confirm)

    def _after_confirm(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        chosen = [
            self._by_key[k] for k, v in self._use.items() if v and k in self._by_key
        ]
        result = backup_and_remove([ex.path for ex in chosen])
        self.notify("\n".join(self._summarise(result)), title="Cleanup", timeout=10)
        self._reload()

    @staticmethod
    def _summarise(result: CleanupResult) -> list[str]:
        msgs = [
            f"[green]✓ Backed up {len(result.backed_up)} · "
            f"deleted {len(result.deleted)}[/green]"
        ]
        if result.backup_dir is not None:
            msgs.append(f"[dim]Backup: {result.backup_dir}[/dim]")
        if result.errors:
            msgs.append(f"[red]{len(result.errors)} error(s):[/red]")
            for path, err in list(result.errors.items())[:6]:
                msgs.append(f"  [red]✗[/red] {path.name}: {err}")
        return msgs

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "cln-apply":
            self.action_clean()
        elif bid == "cln-restore":
            from cabal.views.cleanup_restore import CleanupRestoreScreen

            self.app.push_screen(CleanupRestoreScreen())
