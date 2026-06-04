# -*- coding: utf-8 -*-
"""StatuslineScreen — reorder, toggle, and explain statusline segments."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.statusline_config import load_layout, reset_layout, save_layout


class StatuslineScreen(Screen):
    """Configure which statusline segments show, in what order, and on which row."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+s", "save", "Save"),
        Binding("[", "move_up", "Move up"),
        Binding("]", "move_down", "Move down"),
        Binding("r", "toggle_row", "Row 1/2"),
    ]

    CSS = """
    StatuslineScreen VerticalScroll { width: 1fr; height: 1fr; padding: 0 2; }
    StatuslineScreen #sl-actions { height: 3; margin: 1 0; }
    StatuslineScreen #sl-actions Button { margin: 0 1 0 0; }
    StatuslineScreen #sl-table { width: 1fr; height: 1fr; min-height: 10; }
    StatuslineScreen #sl-desc {
        height: auto;
        padding: 1 2;
        margin: 1 0 0 0;
        background: $boost;
        border: round $primary;
    }
    StatuslineScreen #sl-status { height: auto; margin: 1 0 0 0; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._layout: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]Statusline[/bold bright_magenta]\n"
                "[dim]Pick which segments show in the statusline, reorder them, and move "
                "them between the two rows.\n"
                "Enter / click a row toggles visibility · [b]\\[[/b] / [b]][/b] move up/down · "
                "[b]r[/b] switches row · Ctrl+S saves.[/dim]",
                classes="panel",
            )
            with Horizontal(id="sl-actions"):
                yield Button("Save (Ctrl+S)", id="sl-save", variant="success")
                yield Button("↑ Move up", id="sl-up", variant="default")
                yield Button("↓ Move down", id="sl-down", variant="default")
                yield Button("Toggle row", id="sl-row", variant="default")
                yield Button("Reset to defaults", id="sl-reset", variant="warning")
            yield DataTable(id="sl-table")
            yield Static("", id="sl-desc")
            yield Static("", id="sl-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        self._layout = load_layout()
        tbl = self.query_one("#sl-table", DataTable)
        tbl.cursor_type = "row"
        tbl.add_column("Use", width=6)
        tbl.add_column("Row", width=5)
        tbl.add_column("Segment", width=22)
        tbl.add_column("Description", width=80)
        self._render_table()
        self._update_desc(0)

    @staticmethod
    def _box(symbol: str) -> str:
        return rf"[green]\[{symbol}][/green]"

    def _render_table(self) -> None:
        tbl = self.query_one("#sl-table", DataTable)
        tbl.clear()
        for s in self._layout:
            use = self._box("✓") if s["enabled"] else self._box(" ")
            label = s["label"] if s["enabled"] else f"[dim]{s['label']}[/dim]"
            desc = f"[dim]{s['description']}[/dim]"
            tbl.add_row(use, str(s["row"]), label, desc, key=s["key"])

    def _update_desc(self, index: int | None) -> None:
        if index is None or not (0 <= index < len(self._layout)):
            return
        s = self._layout[index]
        state = "[green]visible[/green]" if s["enabled"] else "[dim]hidden[/dim]"
        self.query_one("#sl-desc", Static).update(
            f"[bold]{s['label']}[/bold]   row {s['row']} · {state}\n[dim]{s['description']}[/dim]"
        )

    def _index_at_cursor(self) -> int | None:
        row = self.query_one("#sl-table", DataTable).cursor_row
        return row if row is not None and 0 <= row < len(self._layout) else None

    def _move(self, delta: int) -> None:
        i = self._index_at_cursor()
        if i is None:
            return
        j = i + delta
        if not (0 <= j < len(self._layout)):
            return
        self._layout[i], self._layout[j] = self._layout[j], self._layout[i]
        self._render_table()
        self.query_one("#sl-table", DataTable).move_cursor(row=j)
        self._update_desc(j)

    def action_move_up(self) -> None:
        self._move(-1)

    def action_move_down(self) -> None:
        self._move(1)

    def action_toggle_row(self) -> None:
        i = self._index_at_cursor()
        if i is None:
            return
        self._layout[i]["row"] = 2 if self._layout[i]["row"] == 1 else 1
        self._render_table()
        self.query_one("#sl-table", DataTable).move_cursor(row=i)
        self._update_desc(i)

    def action_save(self) -> None:
        path = save_layout(self._layout)
        self.query_one("#sl-status", Static).update(
            f"[green]✓ Saved → {path}[/green]\n[bold]→ Restart Claude Code to see the new statusline.[/bold]"
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._update_desc(event.cursor_row)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        for s in self._layout:
            if s["key"] == key:
                s["enabled"] = not s["enabled"]
                break
        self._render_table()
        self.query_one("#sl-table", DataTable).move_cursor(row=event.cursor_row)
        self._update_desc(event.cursor_row)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "sl-save":
            self.action_save()
        elif bid == "sl-up":
            self.action_move_up()
        elif bid == "sl-down":
            self.action_move_down()
        elif bid == "sl-row":
            self.action_toggle_row()
        elif bid == "sl-reset":
            self._layout = reset_layout()
            self._render_table()
            self.query_one("#sl-table", DataTable).move_cursor(row=0)
            self._update_desc(0)
            self.query_one("#sl-status", Static).update(
                "[yellow]Reset to defaults (user config removed).[/yellow]"
            )
