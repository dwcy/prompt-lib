# -*- coding: utf-8 -*-
"""Codex conversion audit and diff screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.codex_setup.conversion import ConversionEntry, audit_conversion_entries
from cabal.widgets.file_viewer import FileViewerModal


class CodexConversionScreen(Screen):
    """Show what was converted from Claude assets into Codex assets."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("v", "view_file", "View"),
    ]

    CSS = """
    CodexConversionScreen #codex-conv-actions { height: auto; }
    CodexConversionScreen .codex-conv-spacer { width: 1fr; }
    CodexConversionScreen #codex-conv-table { max-height: 60; }
    """

    _STATUS_STYLE = {
        "converted": "green",
        "not-converted": "yellow",
        "codex-only": "cyan",
        "stale": "red",
        "unsupported": "magenta",
    }

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_cyan]Codex Conversion Diff[/bold bright_cyan]\n"
                "[dim]Review which Claude assets have Codex counterparts and press v to compare source/output.[/dim]",
                classes="panel",
            )
            with Horizontal(id="codex-conv-actions"):
                yield Button("View (v)", id="codex-conv-view", variant="primary")
                yield Button("Refresh (Ctrl+R)", id="codex-conv-refresh")
                yield Static("", classes="codex-conv-spacer")
                yield Button("Back (Esc)", id="codex-conv-back")
            yield Static("", id="codex-conv-summary")
            yield DataTable(id="codex-conv-table")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._entries: list[ConversionEntry] = []
        table = self.query_one("#codex-conv-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Status", "Kind", "Claude source", "Codex output", "Reason")
        self._refresh()
        table.focus()

    def _refresh(self) -> None:
        self._entries = audit_conversion_entries()
        table = self.query_one("#codex-conv-table", DataTable)
        table.clear()
        counts: dict[str, int] = {}
        for idx, entry in enumerate(self._entries):
            counts[entry.status] = counts.get(entry.status, 0) + 1
            style = self._STATUS_STYLE.get(entry.status, "white")
            table.add_row(
                f"[{style}]{entry.status}[/{style}]",
                entry.kind,
                entry.source_label,
                entry.output_label,
                entry.reason,
                key=str(idx),
            )
        summary = "   ".join(f"{key}: {counts[key]}" for key in sorted(counts))
        self.query_one("#codex-conv-summary", Static).update(
            f"[bold]Entries: {len(self._entries)}[/bold]   {summary}"
        )

    def action_refresh(self) -> None:
        self._refresh()

    def action_view_file(self) -> None:
        table = self.query_one("#codex-conv-table", DataTable)
        if table.row_count == 0:
            return
        try:
            idx = int(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
            entry = self._entries[idx]
        except Exception:
            return

        if entry.status in {"converted", "stale"} and entry.source and entry.output and entry.output.is_file():
            compare = entry.source if entry.source.is_file() else None
            self.app.push_screen(
                FileViewerModal(
                    entry.output,
                    f"{entry.kind}: {entry.source_label} -> {entry.output_label}",
                    compare_path=compare,
                    diff_label="Claude -> Codex",
                )
            )
            return
        if entry.status == "codex-only" and entry.output and entry.output.is_file():
            self.app.push_screen(FileViewerModal(entry.output, entry.output_label))
            return
        if entry.source and entry.source.is_file():
            title = entry.source_label
            if entry.reason:
                title = f"{title} - {entry.reason}"
            self.app.push_screen(FileViewerModal(entry.source, title))
            return
        if entry.source and entry.source.is_dir():
            files = sorted(
                path.relative_to(entry.source).as_posix()
                for path in entry.source.rglob("*")
                if path.is_file()
            )
            listing = "\n".join(f"- {name}" for name in files[:80])
            if len(files) > 80:
                listing += f"\n- ... +{len(files) - 80} more"
            body = (
                f"# {entry.source_label}\n\n"
                f"**Status:** {entry.status}\n\n"
                f"**Reason:** {entry.reason or '(none)'}\n\n"
                "## Files\n\n"
                f"{listing or '(empty directory)'}\n"
            )
            self.app.push_screen(
                FileViewerModal(
                    entry.source,
                    f"{entry.source_label} - {entry.reason}",
                    new_text=body,
                )
            )
            return
        self.notify(
            entry.reason or "No file available for this row.",
            title="View",
            severity="warning",
            timeout=5,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "codex-conv-view":
            self.action_view_file()
        elif bid == "codex-conv-refresh":
            self.action_refresh()
        elif bid == "codex-conv-back":
            self.app.pop_screen()
