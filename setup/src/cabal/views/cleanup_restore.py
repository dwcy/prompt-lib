# -*- coding: utf-8 -*-
"""CleanupRestoreScreen — restore files from a prior cleanup backup into ~/.claude.

The restore counterpart to CleanupScreen, sibling to the settings RestoreScreen: it
lists cleanup backups and copies their files back, skipping any destination that is
newer on disk than its backed-up copy.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, OptionList, Static
from textual.widgets.option_list import Option

from cabal._paths import TARGET
from cabal.app_widgets import AppHeader
from cabal.cleanup_service import list_cleanup_backups, restore_cleanup


class CleanupRestoreScreen(Screen):
    """Pick a cleanup backup and restore its files back into ~/.claude."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Restore a cleanup ✦[/bold bright_magenta]\n"
                f"[dim]Copy files from a cleanup backup back into {TARGET}.[/dim]\n"
                "[dim]A destination that is newer than its backup copy is skipped.[/dim]",
                classes="panel",
            )
            self._backups = list_cleanup_backups()
            if not self._backups:
                yield Static("[yellow]No cleanup backups found.[/yellow]")
            else:
                opts = []
                for b in self._backups:
                    when = self._format_ts(b.timestamp)
                    opts.append(
                        Option(
                            f"{b.timestamp}  ({when}, {b.entry_count} files, "
                            f"{b.total_bytes:,} bytes)",
                            id=str(b.path),
                        )
                    )
                yield OptionList(*opts, id="clnr-list")
                yield Static("")
                with Horizontal():
                    yield Button("Restore selected", id="clnr-apply", variant="warning")
                    yield Button("Back (Esc)", id="clnr-back")
            yield Static("", id="clnr-status", classes="panel")
        yield Footer(show_command_palette=False)

    @staticmethod
    def _format_ts(ts: str) -> str:
        try:
            return datetime.strptime(ts, "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return ts

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "clnr-back":
            self.app.pop_screen()
        elif bid == "clnr-apply":
            self._restore_selected()

    def _restore_selected(self) -> None:
        status = self.query_one("#clnr-status", Static)
        try:
            lst = self.query_one("#clnr-list", OptionList)
        except Exception:
            return
        if lst.highlighted is None:
            status.update("[yellow]Pick a backup first.[/yellow]")
            return
        opt = lst.get_option_at_index(lst.highlighted)
        result = restore_cleanup(Path(opt.id))
        lines = [f"[green]✓ Restored {len(result.restored)} file(s)[/green]"]
        if result.skipped:
            lines.append(
                f"[yellow]Skipped {len(result.skipped)} (newer on disk):[/yellow]"
            )
            for path, reason in result.skipped[:6]:
                lines.append(f"  [yellow]•[/yellow] {path.name} — {reason}")
        if result.errors:
            lines.append(f"[red]{len(result.errors)} error(s):[/red]")
            for path, err in list(result.errors.items())[:6]:
                lines.append(f"  [red]✗[/red] {path.name}: {err}")
        if result.restored:
            lines.append("[bold]→ Restart Claude Code.[/bold]")
        status.update("\n".join(lines))
