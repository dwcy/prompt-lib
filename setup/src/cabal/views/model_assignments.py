# -*- coding: utf-8 -*-
"""ModelAssignmentsScreen — table of agent/skill model pins with inline reassignment."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Footer, OptionList, Static
from textual.widgets.option_list import Option

from cabal._paths import GLOBAL_DIR, TARGET
from cabal.app_widgets import AppHeader
from cabal.model_assignments import (
    ASSIGNABLE_MODELS,
    collect_model_assignments,
    resolves_to,
    set_model,
)


class ModelPickerScreen(ModalScreen[str | None]):
    """Modal list of assignable model values; dismisses with the choice or None."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    DEFAULT_CSS = """
    ModelPickerScreen { align: center middle; }
    ModelPickerScreen #mp-box {
        width: 52; height: auto; padding: 1 2;
        background: $surface; border: round $accent;
    }
    ModelPickerScreen OptionList { height: auto; }
    """

    def __init__(self, kind: str, name: str, current: str) -> None:
        super().__init__()
        self._kind = kind
        self._name = name
        self._current = current

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical

        with Vertical(id="mp-box"):
            yield Static(
                f"[bold]Assign model — {self._kind} [cyan]{self._name}[/cyan][/bold]\n"
                f"[dim]current: {self._current} · esc cancels[/dim]"
            )
            options = []
            for model in ASSIGNABLE_MODELS:
                friendly = resolves_to(model)
                marker = " [green]•[/green]" if model == self._current else ""
                options.append(Option(f"{model} — {friendly}{marker}", id=model))
            yield OptionList(*options)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(event.option.id)


class ModelAssignmentsScreen(Screen):
    """All agents and skills with their `model:` pin; Enter reassigns the row."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "app.pop_screen", "Back"),
        Binding("enter", "assign", "Assign model", show=True, priority=True),
    ]

    def __init__(
        self, global_dir: Path = GLOBAL_DIR, target_dir: Path = TARGET
    ) -> None:
        super().__init__()
        self._global_dir = global_dir
        self._target_dir = target_dir

    def compose(self) -> ComposeResult:
        yield AppHeader()
        yield Static(
            "[bold bright_magenta]✦ Agent & skill model assignments[/bold bright_magenta]\n"
            "[dim]Enter assigns a model to the selected row — the pin is written to the "
            "repo source and mirrored into your ~/.claude folder.[/dim]",
            id="ma-intro",
        )
        table = DataTable(id="ma-table", cursor_type="row", zebra_stripes=True)
        table.add_columns("Kind", "Name", "Model", "Check")
        yield table
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._load_rows()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        self.action_assign()

    def action_assign(self) -> None:
        table = self.query_one("#ma-table", DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return
        kind, name, model_cell, _ = (
            str(cell) for cell in table.get_row_at(table.cursor_row)
        )
        current = model_cell.split(" → ")[0]
        self.app.push_screen(
            ModelPickerScreen(kind, name, current), self._apply_choice(kind, name)
        )

    def _apply_choice(self, kind: str, name: str):
        def apply(choice: str | None) -> None:
            if not choice:
                return
            try:
                written = set_model(
                    kind, name, choice, self._global_dir, self._target_dir
                )
            except (OSError, ValueError) as e:
                self.notify(f"Could not assign: {e}", severity="error")
                return
            targets = ", ".join(str(p) for p in written)
            self.notify(
                f"{kind} {name} → {choice}  ({len(written)} file(s): {targets})"
            )
            self._load_rows(keep_cursor=True)

        return apply

    def _load_rows(self, keep_cursor: bool = False) -> None:
        table = self.query_one("#ma-table", DataTable)
        cursor = table.cursor_row if keep_cursor else 0
        table.clear()
        for row in collect_model_assignments(self._global_dir):
            friendly = resolves_to(row.model)
            shown = row.model + (f" → {friendly}" if friendly else "")
            check = "✓" if row.valid else "✗ unknown value"
            table.add_row(row.kind, row.name, shown, check)
        if table.row_count:
            table.move_cursor(row=min(cursor or 0, table.row_count - 1))
