# -*- coding: utf-8 -*-
"""Global Codex config deploy screen."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.codex_setup.components import CODEX_COMPONENTS, CodexComponent
from cabal.codex_setup.diff_apply import (
    apply_codex_statuses,
    diff_codex_component,
    ensure_codex_target,
    find_codex_extras,
)
from cabal.codex_setup.paths import CODEX_SOURCE_DIR, CODEX_TARGET
from cabal.components import FileStatus
from cabal.widgets.file_viewer import FileViewerModal


class CodexUpdateScreen(Screen):
    """Preview and deploy global/codex into ~/.codex."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("v", "view_file", "View"),
    ]

    CSS = """
    CodexUpdateScreen #codex-upd-actions { height: auto; }
    CodexUpdateScreen .codex-upd-spacer { width: 1fr; }
    CodexUpdateScreen #codex-preview { max-height: 60; }
    """

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_cyan]Global Codex Config[/bold bright_cyan]\n"
                f"[dim]Deploy {CODEX_SOURCE_DIR} -> {CODEX_TARGET}.[/dim]\n"
                "[dim]Only Codex skills and prompt-lib docs are managed; auth, sessions, plugins, and config.toml are left alone.[/dim]",
                classes="panel",
            )
            with Horizontal(id="codex-upd-actions"):
                yield Button("Apply (Ctrl+A)", id="codex-upd-apply", variant="success")
                yield Button("View (v)", id="codex-upd-view", variant="primary")
                yield Static("", classes="codex-upd-spacer")
                yield Button("Back (Esc)", id="codex-upd-back")
            yield Static("", id="codex-update-summary")
            yield DataTable(id="codex-preview")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._use: dict[str, bool] = {}
        self._child_keys: dict[str, list[str]] = {}
        for comp in CODEX_COMPONENTS:
            if not comp.src_path.exists():
                continue
            if comp.type == "file":
                self._use[comp.key] = True
                continue
            keys: list[str] = []
            for _src, rel in sorted(comp.list_files(), key=lambda t: t[1].as_posix()):
                key = self._child_use_key(comp, rel)
                self._use[key] = True
                keys.append(key)
            self._child_keys[comp.key] = keys
        table = self.query_one("#codex-preview", DataTable)
        table.cursor_type = "row"
        table.add_columns("Use", "Component", "Affected")
        self._refresh_preview()
        table.focus()

    @staticmethod
    def _child_use_key(comp: CodexComponent, rel: object) -> str:
        return f"{comp.key}::{Path(rel).as_posix()}"

    @staticmethod
    def _box(symbol: str, color: str = "green") -> str:
        return rf"[{color}]\[{symbol}][/{color}]"

    def _parent_state(self, comp: CodexComponent) -> str:
        keys = self._child_keys.get(comp.key, [])
        if not keys:
            return "empty"
        selected = sum(1 for key in keys if self._use.get(key))
        if selected == 0:
            return "none"
        if selected == len(keys):
            return "all"
        return "partial"

    def _parent_cell(self, comp: CodexComponent) -> str:
        return {
            "all": self._box("x"),
            "none": self._box(" "),
            "partial": self._box("~"),
            "empty": self._box(" ", "dim"),
        }[self._parent_state(comp)]

    def _leaf_cell(self, use_key: str) -> str:
        return self._box("x") if self._use.get(use_key) else self._box(" ")

    @staticmethod
    def _yellow(text: str, changed: bool) -> str:
        return f"[yellow]{text}[/yellow]" if changed else text

    @staticmethod
    def _detail(state: str) -> str:
        return "[dim]up to date[/dim]" if state == "UNCHANGED" else f"[yellow]{state.lower()}[/yellow]"

    def _refresh_preview(self) -> None:
        table = self.query_one("#codex-preview", DataTable)
        table.clear()
        totals = {"new": 0, "changed": 0, "unchanged": 0}
        used = 0
        for comp in CODEX_COMPONENTS:
            if not comp.src_path.exists():
                table.add_row(
                    self._box("!", "red"),
                    comp.label,
                    "[red](missing in repo)[/red]",
                    key=comp.key,
                )
                continue
            statuses = diff_codex_component(comp)
            if comp.type == "file":
                state = statuses[0].state if statuses else "UNCHANGED"
                if self._use.get(comp.key):
                    totals["new"] += state == "NEW"
                    totals["changed"] += state == "CHANGED"
                    totals["unchanged"] += state == "UNCHANGED"
                    used += 1
                table.add_row(
                    self._leaf_cell(comp.key),
                    self._yellow(comp.label, state != "UNCHANGED"),
                    self._detail(state),
                    key=comp.key,
                )
                continue

            by_rel = {Path(status.rel).as_posix(): status for status in statuses}
            affected = [status.rel for status in statuses if status.state != "UNCHANGED"]
            names = ", ".join(str(path) for path in affected[:3])
            if len(affected) > 3:
                names += f", ... +{len(affected) - 3}"
            child_keys = self._child_keys.get(comp.key, [])
            table.add_row(
                self._parent_cell(comp),
                self._yellow(f"[bold]{comp.label}[/bold] ({len(child_keys)})", bool(affected)),
                self._yellow(names, bool(affected)) if names else "[dim]up to date[/dim]",
                key=comp.key,
            )
            for key in child_keys:
                rel_path = key.split("::", 1)[1]
                status = by_rel.get(rel_path)
                state = status.state if status else "UNCHANGED"
                if self._use.get(key):
                    totals["new"] += state == "NEW"
                    totals["changed"] += state == "CHANGED"
                    totals["unchanged"] += state == "UNCHANGED"
                    used += 1
                table.add_row(
                    self._leaf_cell(key),
                    self._yellow(f"  - {rel_path}", state != "UNCHANGED"),
                    self._detail(state),
                    key=key,
                )
            for extra in sorted(find_codex_extras(comp), key=lambda p: p.as_posix()):
                rel = extra.as_posix()
                table.add_row(
                    self._box("!", "red"),
                    f"[red]  - {rel}[/red]",
                    "[red]not from this repo[/red]",
                    key=f"extra::{comp.key}::{rel}",
                )
        self.query_one("#codex-update-summary", Static).update(
            f"[bold]Selected: {used} files[/bold]   "
            f"[green]NEW {totals['new']}[/green]   "
            f"[yellow]CHANGED {totals['changed']}[/yellow]   "
            f"[dim]UNCHANGED {totals['unchanged']}[/dim]"
        )

    def _selected_statuses(self, comp: CodexComponent) -> list[FileStatus]:
        if not comp.src_path.exists():
            return []
        statuses = diff_codex_component(comp)
        if comp.type == "file":
            return statuses if self._use.get(comp.key) else []
        return [
            status
            for status in statuses
            if self._use.get(self._child_use_key(comp, status.rel))
        ]

    def _resolve_row_view(self, key: str) -> tuple[Path | None, Path | None, str]:
        if key.startswith("extra::"):
            _, comp_key, rel = key.split("::", 2)
            comp = next((item for item in CODEX_COMPONENTS if item.key == comp_key), None)
            if comp is None:
                return None, None, "Unknown row"
            return None, comp.dst_path / rel, rel
        if "::" in key:
            parent_key, rel = key.split("::", 1)
            comp = next((item for item in CODEX_COMPONENTS if item.key == parent_key), None)
            if comp is None:
                return None, None, "Unknown row"
            return comp.src_path / rel, comp.dst_path / rel, rel
        comp = next((item for item in CODEX_COMPONENTS if item.key == key), None)
        if comp is None:
            return None, None, "Unknown row"
        if comp.type == "file":
            return comp.src_path, comp.dst_path, comp.label
        return None, None, f"{comp.label} is a group - expand it and press v on a file row"

    def action_view_file(self) -> None:
        table = self.query_one("#codex-preview", DataTable)
        if table.row_count == 0:
            return
        try:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return
        src, dst, label = self._resolve_row_view(key or "")
        if src is None and dst is None:
            self.notify(label, title="View", severity="information", timeout=4)
            return
        if src is None:
            self.app.push_screen(FileViewerModal(dst, label))
            return
        compare = dst if (dst is not None and dst.is_file()) else None
        self.app.push_screen(FileViewerModal(src, label, compare_path=compare))

    def action_refresh(self) -> None:
        self._refresh_preview()

    def action_apply(self) -> None:
        selected = [(comp, self._selected_statuses(comp)) for comp in CODEX_COMPONENTS]
        selected = [(comp, statuses) for comp, statuses in selected if statuses]
        if not selected:
            self.notify("Nothing selected.", severity="warning", timeout=4)
            return
        ensure_codex_target()
        msgs: list[str] = []
        for comp, statuses in selected:
            copied, skipped = apply_codex_statuses(statuses)
            msgs.append(
                f"  [green]OK[/green] {comp.label}: {copied} copied, {skipped} unchanged"
            )
        msgs.append(
            "[bold green]OK Apply complete.[/bold green]  [bold]Restart Codex to reload skills.[/bold]"
        )
        self.notify("\n".join(msgs), title="Apply", timeout=8)
        self._refresh_preview()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        if key.startswith("extra::"):
            return
        if "::" in key:
            self._use[key] = not self._use.get(key, False)
        else:
            comp = next((item for item in CODEX_COMPONENTS if item.key == key), None)
            if comp is None or not comp.src_path.exists():
                return
            if comp.type == "file":
                self._use[key] = not self._use.get(key, False)
            else:
                turn_on = self._parent_state(comp) != "all"
                for child_key in self._child_keys.get(key, []):
                    self._use[child_key] = turn_on
        self._refresh_preview()
        self.query_one("#codex-preview", DataTable).move_cursor(row=event.cursor_row)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "codex-upd-apply":
            self.action_apply()
        elif bid == "codex-upd-view":
            self.action_view_file()
        elif bid == "codex-upd-back":
            self.app.pop_screen()
