# -*- coding: utf-8 -*-
"""Local Codex project setup screen."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Footer, Select, Static

from cabal.app_widgets import AppHeader
from cabal.codex_setup.local_setup import (
    apply_codex_local_group,
    build_codex_local_plan,
    format_codex_project_status,
)
from cabal.codex_setup.paths import CODEX_SOURCE_DIR
from cabal.widgets.file_viewer import FileViewerModal


class CodexLocalScreen(Screen):
    """Scaffold .agents/ and AGENTS.md in the selected project."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
        Binding("v", "view_file", "View"),
    ]

    def __init__(self) -> None:
        super().__init__()
        tpls = (
            sorted((CODEX_SOURCE_DIR / "project-templates").glob("*.md"))
            if (CODEX_SOURCE_DIR / "project-templates").exists()
            else []
        )
        self.template_options = [(path.stem, str(path)) for path in tpls]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_cyan]Local Codex Config[/bold bright_cyan]\n"
                "[dim]Create project-local Codex guidance and skills without touching .claude/.[/dim]",
                classes="panel",
            )
            yield Static(
                f"[bold]Project path:[/bold] {self.app.project_path()}",
                classes="panel",
            )
            yield Checkbox(
                "Create .agents/ scaffolding (skills/)",
                value=True,
                id="codex-loc-scaffold",
            )
            yield Checkbox(
                "Apply AGENTS.md project template",
                value=False,
                id="codex-loc-template",
            )
            if self.template_options:
                yield Select(
                    self.template_options,
                    id="codex-loc-tpl-select",
                    prompt="Pick template...",
                )
            yield Checkbox(
                "Sync skills: global/codex/skills -> .agents/skills",
                value=False,
                id="codex-loc-skills",
            )
            yield Static("", id="codex-loc-proj-status", classes="panel")
            yield DataTable(id="codex-loc-preview")
            with Horizontal():
                yield Button("Refresh preview", id="codex-loc-refresh")
                yield Button("View (v)", id="codex-loc-view", variant="primary")
                yield Button("Apply (Ctrl+A)", id="codex-loc-apply", variant="success")
                yield Button("Back (Esc)", id="codex-loc-back")
            yield Static("", id="codex-loc-status", classes="panel")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._use: dict[str, bool] = {}
        self._child_keys: dict[str, list[str]] = {}
        self._row_op: dict[str, dict] = {}
        table = self.query_one("#codex-loc-preview", DataTable)
        table.cursor_type = "row"
        table.add_columns("Use", "Item", "State")
        self._refresh()

    @staticmethod
    def _box(symbol: str, color: str = "green") -> str:
        return rf"[{color}]\[{symbol}][/{color}]"

    def _parent_state(self, action: str) -> str:
        keys = self._child_keys.get(action, [])
        if not keys:
            return "empty"
        selected = sum(1 for key in keys if self._use.get(key))
        if selected == 0:
            return "none"
        if selected == len(keys):
            return "all"
        return "partial"

    def _parent_cell(self, action: str) -> str:
        return {
            "all": self._box("x"),
            "none": self._box(" "),
            "partial": self._box("~"),
            "empty": self._box(" ", "dim"),
        }[self._parent_state(action)]

    def _leaf_cell(self, key: str) -> str:
        return self._box("x") if self._use.get(key) else self._box(" ")

    def _selected(self) -> dict[str, bool]:
        return {
            "scaffold": self.query_one("#codex-loc-scaffold", Checkbox).value,
            "template": self.query_one("#codex-loc-template", Checkbox).value,
            "skills": self.query_one("#codex-loc-skills", Checkbox).value,
        }

    def _template_path(self) -> Path | None:
        if not self.template_options:
            return None
        try:
            select = self.query_one("#codex-loc-tpl-select", Select)
        except Exception:
            return None
        if not isinstance(select.value, str):
            return None
        return Path(select.value)

    def _plan(self) -> list[dict]:
        selected = self._selected()
        return build_codex_local_plan(
            self.app.project_path(),
            selected,
            self._template_path() if selected["template"] else None,
        )

    def _refresh(self) -> None:
        table = self.query_one("#codex-loc-preview", DataTable)
        table.clear()
        self._child_keys = {}
        self._row_op = {}
        project = self.app.project_path()
        status = self.query_one("#codex-loc-proj-status", Static)
        if not project.exists() or not project.is_dir():
            status.update(f"[red]Path not a directory:[/red] {project}")
            return
        status.update(format_codex_project_status(project))
        for group in self._plan():
            action = group["action"]
            selectable = [child for child in group["children"] if child["op"] is not None]
            for child in selectable:
                self._use.setdefault(child["key"], True)
            self._child_keys[action] = [child["key"] for child in selectable]
            table.add_row(
                self._parent_cell(action),
                f"[bold]{group['label']}[/bold]",
                "",
                key=f"action::{action}",
            )
            for idx, child in enumerate(group["children"]):
                if child["op"] is None:
                    row_key = f"noop::{action}::{idx}"
                    box = self._box(" ", "dim")
                else:
                    row_key = child["key"]
                    box = self._leaf_cell(row_key)
                self._row_op[row_key] = child
                table.add_row(box, f"  - {child['label']}", child["state"], key=row_key)

    def action_view_file(self) -> None:
        table = self.query_one("#codex-loc-preview", DataTable)
        if table.row_count == 0:
            return
        try:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return
        if (key or "").startswith("action::"):
            self.notify("Expand the group and press v on a file row.", title="View", timeout=4)
            return
        child = self._row_op.get(key or "")
        op = child["op"] if child else None
        if op and op[0] == "copy":
            _, src, dst = op
            self.app.push_screen(
                FileViewerModal(
                    src,
                    str(child["label"]),
                    compare_path=dst if dst.is_file() else None,
                )
            )
            return
        if op and op[0] == "copy_tree":
            _, src, dst = op
            source_skill = src / "SKILL.md"
            target_skill = dst / "SKILL.md"
            self.app.push_screen(
                FileViewerModal(
                    source_skill,
                    str(child["label"]),
                    compare_path=target_skill if target_skill.is_file() else None,
                )
            )
            return
        self.notify("No file diff for this operation.", title="View", severity="information", timeout=4)

    def action_apply(self) -> None:
        project = self.app.project_path()
        if not project.is_dir():
            self.query_one("#codex-loc-status", Static).update(
                f"[red]Not a directory:[/red] {project}"
            )
            return
        msgs: list[str] = []
        for group in self._plan():
            chosen = [
                child
                for child in group["children"]
                if child["op"] is not None and self._use.get(child["key"])
            ]
            if chosen:
                msgs.extend(apply_codex_local_group(group["action"], chosen))
        if not msgs:
            msgs.append("[yellow]Nothing selected.[/yellow]")
        self.query_one("#codex-loc-status", Static).update("\n".join(msgs))
        self._refresh()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        if key.startswith("noop::"):
            return
        if key.startswith("action::"):
            action = key.split("::", 1)[1]
            kids = self._child_keys.get(action, [])
            if not kids:
                return
            turn_on = self._parent_state(action) != "all"
            for child_key in kids:
                self._use[child_key] = turn_on
        else:
            self._use[key] = not self._use.get(key, False)
        self._refresh()
        self.query_one("#codex-loc-preview", DataTable).move_cursor(row=event.cursor_row)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._refresh()

    def on_select_changed(self, event: Select.Changed) -> None:
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "codex-loc-back":
            self.app.pop_screen()
        elif bid == "codex-loc-refresh":
            self._refresh()
        elif bid == "codex-loc-view":
            self.action_view_file()
        elif bid == "codex-loc-apply":
            self.action_apply()
