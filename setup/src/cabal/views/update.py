# -*- coding: utf-8 -*-
"""UpdateScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

from __future__ import annotations

import filecmp
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from rich.markup import escape as escape_markup
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import (
    Center,
    Container,
    Horizontal,
    ScrollableContainer,
    Vertical,
    VerticalScroll,
)
from textual.coordinate import Coordinate
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    MarkdownViewer,
    OptionList,
    RadioButton,
    RadioSet,
    Rule,
    Select,
    Static,
)
from textual.widgets.option_list import Option
from textual.widget import Widget

from cabal._paths import GLOBAL_DIR, TARGET, REPO_DIR, ENV_DIR, ENV_FILE, RESOURCE_ROOT
from cabal.app_widgets import AppHeader
from cabal.banner import HexBanner, render_banner
from cabal.components import COMPONENTS, Component, ENV_DESCRIPTIONS, FileStatus
from cabal.diff_apply import (
    apply_statuses,
    backup_settings,
    diff_component,
    find_extras,
    prune_backups,
)
from cabal.env_detect import detect_env, find_env_vars
from cabal.env_summary import render_env_summary
from cabal.git_config import apply_git_line_endings, recommended_autocrlf
from cabal.installers.gh import gh_device_init, gh_device_poll, gh_fetch_token
from cabal.mcp_ops import (
    claude_mcp_add_from_template,
    claude_mcp_remove,
    enumerate_mcp_servers,
)
from cabal.tools import (
    ENV_INSTALLERS,
    ENV_TOOL_GROUPS,
    TOOLS,
    Tool,
    VERSION_FLOORS,
    WINGET_IDS,
    _below_floor,
    _installer_for,
    _outdated_packages,
    _probe_key,
)
from cabal.updates import check_for_updates, do_git_pull
from cabal.views.restore import RestoreScreen
from cabal.widgets.env_panel import EnvPanel
from cabal.widgets.file_viewer import FileViewerModal
from cabal.widgets.update_panel import UpdatePanel


class UpdateScreen(Screen):
    """Multi-select components, preview diff, then apply."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("v", "view_file", "View"),
    ]

    CSS = """
    UpdateScreen #upd-actions { height: auto; }
    UpdateScreen .upd-spacer { width: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]Global Claude Settings[/bold bright_magenta]\n"
                f"[dim]Deploy {GLOBAL_DIR} → {TARGET}.[/dim]\n"
                "[dim]Enter (or click) toggles Use · [b]v[/b] views the highlighted file · Apply (Ctrl+A).[/dim]",
                classes="panel",
            )
            with Horizontal(id="upd-actions"):
                yield Button("Apply (Ctrl+A)", id="upd-apply", variant="success")
                yield Static("", classes="upd-spacer")
                yield Button("Restore", id="upd-restore", variant="warning")
            yield Static("", id="update-summary")
            yield DataTable(id="preview")
            yield Static("", id="upd-status", classes="panel")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._use: dict[str, bool] = {}
        self._child_keys: dict[str, list[str]] = {}
        for c in COMPONENTS:
            if not c.src_path.exists():
                continue
            if c.type == "file":
                self._use[c.key] = True
                continue
            keys: list[str] = []
            for _src, rel in sorted(c.list_files(), key=lambda t: t[1].as_posix()):
                k = self._child_use_key(c, rel)
                self._use[k] = True
                keys.append(k)
            self._child_keys[c.key] = keys
        tbl = self.query_one("#preview", DataTable)
        tbl.cursor_type = "row"
        tbl.add_columns("Use", "Component", "Affected")
        self._refresh_preview()
        tbl.focus()

    def action_view_file(self) -> None:
        """Open the file under the cursor in a read-only modal (markdown rendered)."""
        tbl = self.query_one("#preview", DataTable)
        if tbl.row_count == 0:
            return
        try:
            key = tbl.coordinate_to_cell_key(tbl.cursor_coordinate).row_key.value
        except Exception:
            return
        path, label = self._resolve_row_path(key or "")
        if path is None:
            self.notify(label, title="View", severity="information", timeout=4)
            return
        self.app.push_screen(FileViewerModal(path, label))

    def _resolve_row_path(self, key: str) -> tuple[Path | None, str]:
        """Map a DataTable row key to its source file path, or (None, hint)."""
        if "::" in key:
            parent_key, rel = key.split("::", 1)
            c = next((c for c in COMPONENTS if c.key == parent_key), None)
            if c is None:
                return None, "Unknown row"
            p = c.src_path / rel
            return (p, rel) if p.is_file() else (None, f"File not found: {rel}")
        c = next((c for c in COMPONENTS if c.key == key), None)
        if c is None:
            return None, "Unknown row"
        if c.type == "file":
            return (
                (c.src_path, c.label)
                if c.src_path.is_file()
                else (None, f"Not found: {c.label}")
            )
        return None, f"{c.label} is a group — expand it and press v on a file row"

    @staticmethod
    def _child_use_key(c: Component, rel: object) -> str:
        return f"{c.key}::{Path(rel).as_posix()}"

    def _parent_state(self, c: Component) -> str:
        keys = self._child_keys.get(c.key, [])
        if not keys:
            return "empty"
        selected = sum(1 for k in keys if self._use.get(k))
        if selected == 0:
            return "none"
        if selected == len(keys):
            return "all"
        return "partial"

    @staticmethod
    def _box(symbol: str, color: str = "green") -> str:
        return rf"[{color}]\[{symbol}][/{color}]"

    def _parent_cell(self, c: Component) -> str:
        if not c.src_path.exists():
            return self._box("✗", "red")
        return {
            "all": self._box("✓"),
            "none": self._box(" "),
            "partial": self._box("~"),
            "empty": self._box(" "),
        }[self._parent_state(c)]

    def _leaf_cell(self, use_key: str) -> str:
        return self._box("✓") if self._use.get(use_key) else self._box(" ")

    @staticmethod
    def _yellow(text: str, changed: bool) -> str:
        return f"[yellow]{text}[/yellow]" if changed else text

    @staticmethod
    def _child_detail(state: str) -> str:
        if state == "UNCHANGED":
            return "[dim]up to date[/dim]"
        return f"[yellow]{state.lower()}[/yellow]"

    def _refresh_preview(self) -> None:
        tbl = self.query_one("#preview", DataTable)
        tbl.clear()
        totals = {"new": 0, "changed": 0, "unchanged": 0}
        used = 0
        for c in COMPONENTS:
            if not c.src_path.exists():
                tbl.add_row(
                    self._parent_cell(c),
                    c.label,
                    "[red](missing in repo)[/red]",
                    key=c.key,
                )
                continue
            statuses = diff_component(c)
            if c.type == "file":
                state = statuses[0].state if statuses else "UNCHANGED"
                changed = state != "UNCHANGED"
                if self._use.get(c.key):
                    totals["new"] += state == "NEW"
                    totals["changed"] += state == "CHANGED"
                    totals["unchanged"] += state == "UNCHANGED"
                    used += 1
                tbl.add_row(
                    self._leaf_cell(c.key),
                    self._yellow(c.label, changed),
                    self._child_detail(state),
                    key=c.key,
                )
                continue
            by_rel = {Path(s.rel).as_posix(): s for s in statuses}
            all_chg = sum(1 for s in statuses if s.state != "UNCHANGED")
            affected = [s.rel for s in statuses if s.state != "UNCHANGED"]
            names = ", ".join(str(p) for p in affected[:3])
            if len(affected) > 3:
                names += f", … +{len(affected) - 3}"
            parent_changed = all_chg > 0
            names = (
                self._yellow(names, parent_changed)
                if names
                else "[dim]up to date[/dim]"
            )
            child_keys = self._child_keys.get(c.key, [])
            tbl.add_row(
                self._parent_cell(c),
                self._yellow(
                    f"[bold]{c.label}[/bold] ({len(child_keys)})", parent_changed
                ),
                names,
                key=c.key,
            )
            for k in child_keys:
                relp = k.split("::", 1)[1]
                st = by_rel.get(relp)
                state = st.state if st else "UNCHANGED"
                changed = state != "UNCHANGED"
                if self._use.get(k):
                    totals["new"] += state == "NEW"
                    totals["changed"] += state == "CHANGED"
                    totals["unchanged"] += state == "UNCHANGED"
                    used += 1
                tbl.add_row(
                    self._leaf_cell(k),
                    self._yellow(f"  └ {relp}", changed),
                    self._child_detail(state),
                    key=k,
                )
        self.query_one("#update-summary", Static).update(
            f"[bold]Selected: {used} files[/bold]   "
            f"[green]NEW {totals['new']}[/green]   "
            f"[yellow]CHANGED {totals['changed']}[/yellow]   "
            f"[dim]UNCHANGED {totals['unchanged']}[/dim]"
        )

    def _selected_statuses(self, c: Component) -> list[FileStatus]:
        if not c.src_path.exists():
            return []
        statuses = diff_component(c)
        if c.type == "file":
            return statuses if self._use.get(c.key) else []
        return [s for s in statuses if self._use.get(self._child_use_key(c, s.rel))]

    def action_refresh(self) -> None:
        self._refresh_preview()

    def action_apply(self) -> None:
        selected = [(c, self._selected_statuses(c)) for c in COMPONENTS]
        selected = [(c, sts) for c, sts in selected if sts]
        if not selected:
            self.query_one("#upd-status", Static).update(
                "[yellow]Nothing selected.[/yellow]"
            )
            return
        msgs = []
        if self._use.get("settings"):
            bk = backup_settings()
            if bk:
                msgs.append(f"[dim]Backed up settings.json → {bk.name}[/dim]")
            prune_backups(10)
        TARGET.mkdir(parents=True, exist_ok=True)
        for c, sts in selected:
            copied, skipped = apply_statuses(sts)
            msgs.append(
                f"  [green]✓[/green] {c.label}: {copied} copied, {skipped} unchanged"
            )
        msgs.append(
            "\n[bold green]✓ Apply complete.[/bold green]  [bold]→ Restart Claude Code.[/bold]"
        )
        self.query_one("#upd-status", Static).update("\n".join(msgs))
        self._refresh_preview()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        if "::" in key:
            self._use[key] = not self._use.get(key, False)
        else:
            c = next((c for c in COMPONENTS if c.key == key), None)
            if c is None or not c.src_path.exists():
                return
            if c.type == "file":
                self._use[key] = not self._use.get(key, False)
            else:
                turn_on = self._parent_state(c) != "all"
                for k in self._child_keys.get(key, []):
                    self._use[k] = turn_on
        self._refresh_preview()
        self.query_one("#preview", DataTable).move_cursor(row=event.cursor_row)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "upd-apply":
            self.action_apply()
        elif bid == "upd-restore":
            self.app.push_screen(RestoreScreen())
