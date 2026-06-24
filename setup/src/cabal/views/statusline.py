# -*- coding: utf-8 -*-
"""StatuslineScreen — reorder, toggle, and explain statusline segments.

Segments are shown in two grouped tables (Row 1 / Row 2); `r` moves the
highlighted segment to the other group.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
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
        Binding("r", "swap_group", "Move row"),
    ]

    CSS = """
    StatuslineScreen VerticalScroll { width: 1fr; height: 1fr; padding: 0 2; }
    StatuslineScreen #sl-actions { height: 3; margin: 1 0; }
    StatuslineScreen #sl-actions Button { margin: 0 1 0 0; }
    StatuslineScreen .sl-group-title {
        text-style: bold;
        color: #5FAFFF;
        margin: 1 0 0 0;
    }
    StatuslineScreen .sl-table {
        width: 1fr;
        height: auto;
        max-height: 20;
        margin: 0 0 1 0;
    }
    StatuslineScreen #sl-desc {
        height: auto;
        padding: 1 2;
        margin: 1 0 0 0;
        background: $boost;
        border: round #CC006B;
    }
    StatuslineScreen #sl-status { height: auto; margin: 1 0 0 0; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._rows: dict[int, list[dict[str, Any]]] = {1: [], 2: []}
        self._active_row: int = 1

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]Statusline[/bold bright_magenta]\n"
                "[dim]Pick which segments show, reorder within each row, and move segments "
                "between Row 1 and Row 2.\n"
                "Enter / click toggles visibility · [b]\\[[/b] / [b]][/b] move up/down · "
                "[b]r[/b] moves a segment to the other row · Ctrl+S saves.[/dim]",
                classes="panel",
            )
            with Horizontal(id="sl-actions"):
                yield Button("Save (Ctrl+S)", id="sl-save", variant="success")
                yield Button("↑ Move up", id="sl-up", variant="default")
                yield Button("↓ Move down", id="sl-down", variant="default")
                yield Button("Move to other row", id="sl-row", variant="default")
                yield Button("Reset to defaults", id="sl-reset", variant="warning")
            yield Static("✦ Row 1", classes="sl-group-title")
            yield DataTable(id="sl-table-1", classes="sl-table")
            yield Static("✦ Row 2", classes="sl-group-title")
            yield DataTable(id="sl-table-2", classes="sl-table")
            yield Static("", id="sl-desc")
            yield Static("", id="sl-status", classes="panel")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._split_layout(load_layout())
        for r in (1, 2):
            tbl = self.query_one(f"#sl-table-{r}", DataTable)
            tbl.cursor_type = "row"
            tbl.add_column("Use", width=6)
            tbl.add_column("Group", width=10)
            tbl.add_column("Segment", width=22)
            tbl.add_column("Description", width=80)
        self._fill_tables()
        self.query_one("#sl-table-1", DataTable).focus()
        self._update_desc(1, 0)

    def _split_layout(self, layout: list[dict[str, Any]]) -> None:
        self._rows = {1: [], 2: []}
        for s in layout:
            self._rows[2 if s.get("row") == 2 else 1].append(s)

    _GROUP_STYLE = {"Claude": "magenta", "Git": "green", "Project": "cyan"}

    @staticmethod
    def _box(symbol: str) -> str:
        return rf"[green]\[{symbol}][/green]"

    def _group_cell(self, group: str) -> str:
        if not group:
            return ""
        return f"[{self._GROUP_STYLE.get(group, 'white')}]{group}[/]"

    def _fill_tables(self) -> None:
        for r in (1, 2):
            self._fill_row(r)

    def _fill_row(self, r: int) -> None:
        tbl = self.query_one(f"#sl-table-{r}", DataTable)
        tbl.clear()
        for s in self._rows[r]:
            use = self._box("✓") if s["enabled"] else self._box(" ")
            group = self._group_cell(s.get("group", ""))
            label = s["label"] if s["enabled"] else f"[dim]{s['label']}[/dim]"
            desc = f"[dim]{s['description']}[/dim]"
            tbl.add_row(use, group, label, desc, key=s["key"])

    @staticmethod
    def _table_row(table: DataTable) -> int:
        return 1 if (table.id or "").endswith("-1") else 2

    def _update_desc(self, r: int, index: int | None) -> None:
        lst = self._rows[r]
        if index is None or not (0 <= index < len(lst)):
            self.query_one("#sl-desc", Static).update("")
            return
        s = lst[index]
        state = "[green]visible[/green]" if s["enabled"] else "[dim]hidden[/dim]"
        self.query_one("#sl-desc", Static).update(
            f"[bold]{s['label']}[/bold]   row {r} · {state}\n[dim]{s['description']}[/dim]"
        )

    def _move(self, delta: int) -> None:
        r = self._active_row
        tbl = self.query_one(f"#sl-table-{r}", DataTable)
        i = tbl.cursor_row
        lst = self._rows[r]
        j = (i if i is not None else -1) + delta
        if i is None or not (0 <= i < len(lst)) or not (0 <= j < len(lst)):
            return
        lst[i], lst[j] = lst[j], lst[i]
        self._fill_row(r)
        tbl.move_cursor(row=j)
        self._update_desc(r, j)

    def action_move_up(self) -> None:
        self._move(-1)

    def action_move_down(self) -> None:
        self._move(1)

    def action_swap_group(self) -> None:
        r = self._active_row
        tbl = self.query_one(f"#sl-table-{r}", DataTable)
        i = tbl.cursor_row
        lst = self._rows[r]
        if i is None or not (0 <= i < len(lst)):
            return
        seg = lst.pop(i)
        other = 2 if r == 1 else 1
        seg["row"] = other
        self._rows[other].append(seg)
        self._fill_tables()
        self._active_row = other
        otbl = self.query_one(f"#sl-table-{other}", DataTable)
        otbl.focus()
        last = len(self._rows[other]) - 1
        if last >= 0:
            otbl.move_cursor(row=last)
        self._update_desc(other, last)

    def action_save(self) -> None:
        layout: list[dict[str, Any]] = []
        for r in (1, 2):
            for s in self._rows[r]:
                s["row"] = r
                layout.append(s)
        path = save_layout(layout)
        self.query_one("#sl-status", Static).update(
            f"[green]✓ Saved → {path}[/green]\n"
            "[bold]→ Restart Claude Code to see the new statusline.[/bold]"
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        r = self._table_row(event.data_table)
        self._active_row = r
        self._update_desc(r, event.cursor_row)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        r = self._table_row(event.data_table)
        key = event.row_key.value
        for s in self._rows[r]:
            if s["key"] == key:
                s["enabled"] = not s["enabled"]
                break
        self._fill_row(r)
        event.data_table.move_cursor(row=event.cursor_row)
        self._update_desc(r, event.cursor_row)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "sl-save":
            self.action_save()
        elif bid == "sl-up":
            self.action_move_up()
        elif bid == "sl-down":
            self.action_move_down()
        elif bid == "sl-row":
            self.action_swap_group()
        elif bid == "sl-reset":
            self._split_layout(reset_layout())
            self._fill_tables()
            self._active_row = 1
            self.query_one("#sl-table-1", DataTable).focus()
            t1 = self.query_one("#sl-table-1", DataTable)
            if self._rows[1]:
                t1.move_cursor(row=0)
            self._update_desc(1, 0 if self._rows[1] else None)
            self.query_one("#sl-status", Static).update(
                "[yellow]Reset to defaults (user config removed).[/yellow]"
            )
