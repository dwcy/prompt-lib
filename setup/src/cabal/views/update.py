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
from textual.containers import Center, Container, Horizontal, ScrollableContainer, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button, Checkbox, DataTable, Footer, Header, Input, Label,
    MarkdownViewer, OptionList, RadioButton, RadioSet, Rule, Select, Static,
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
from cabal.widgets.update_panel import UpdatePanel

class UpdateScreen(Screen):
    """Multi-select components, preview diff, then apply."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Configure global settings ✦[/bold bright_magenta]\n"
                f"[dim]Deploy {GLOBAL_DIR} → {TARGET}.[/dim]\n"
                "[dim]Toggle components, then Apply (Ctrl+A).[/dim]",
                classes="panel",
            )
            yield Static("", id="update-summary")
            for c in COMPONENTS:
                files = c.list_files()
                count = f" ({len(files)})" if c.type == "dir" else ""
                missing = "" if c.src_path.exists() else "  [red](missing in repo)[/red]"
                yield Checkbox(
                    f"{c.label}{count}{missing}",
                    value=c.src_path.exists(),
                    id=f"cb-{c.key}",
                    disabled=not c.src_path.exists(),
                )
            yield Static("")
            yield DataTable(id="preview", show_cursor=False)
            yield Static("")
            with Horizontal():
                yield Button("Refresh preview (Ctrl+R)", id="upd-refresh")
                yield Button("Apply (Ctrl+A)", id="upd-apply", variant="success")
                yield Button("Restore", id="upd-restore", variant="warning")
            yield Static("", id="upd-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#preview", DataTable)
        tbl.add_columns("Component", "New", "Changed", "Unchanged", "Affected")
        self._refresh_preview()

    def _selected_components(self) -> list[Component]:
        out = []
        for c in COMPONENTS:
            cb = self.query_one(f"#cb-{c.key}", Checkbox)
            if cb.value and not cb.disabled:
                out.append(c)
        return out

    def _refresh_preview(self) -> None:
        tbl = self.query_one("#preview", DataTable)
        tbl.clear()
        comps = self._selected_components()
        totals = {"new": 0, "changed": 0, "unchanged": 0}
        for c in comps:
            statuses = diff_component(c)
            new = sum(1 for s in statuses if s.state == "NEW")
            chg = sum(1 for s in statuses if s.state == "CHANGED")
            unc = sum(1 for s in statuses if s.state == "UNCHANGED")
            totals["new"] += new
            totals["changed"] += chg
            totals["unchanged"] += unc
            affected = [s.rel for s in statuses if s.state != "UNCHANGED"]
            names = ", ".join(str(p) for p in affected[:3])
            if len(affected) > 3:
                names += f", … +{len(affected) - 3}"
            tbl.add_row(
                c.label,
                str(new) if new else "·",
                str(chg) if chg else "·",
                str(unc) if unc else "·",
                names if names else "[dim]up to date[/dim]",
            )
        self.query_one("#update-summary", Static).update(
            f"[bold]Selected: {len(comps)} components[/bold]   "
            f"[green]NEW {totals['new']}[/green]   "
            f"[yellow]CHANGED {totals['changed']}[/yellow]   "
            f"[dim]UNCHANGED {totals['unchanged']}[/dim]"
        )

    def action_refresh(self) -> None:
        self._refresh_preview()

    def action_apply(self) -> None:
        comps = self._selected_components()
        if not comps:
            self.query_one("#upd-status", Static).update("[yellow]Nothing selected.[/yellow]")
            return
        msgs = []
        if any(c.key == "settings" for c in comps):
            bk = backup_settings()
            if bk:
                msgs.append(f"[dim]Backed up settings.json → {bk.name}[/dim]")
            prune_backups(10)
        TARGET.mkdir(parents=True, exist_ok=True)
        total_copied = total_skipped = 0
        for c in comps:
            statuses = diff_component(c)
            copied, skipped = apply_statuses(statuses)
            total_copied += copied
            total_skipped += skipped
            msgs.append(f"  [green]✓[/green] {c.label}: {copied} copied, {skipped} unchanged")
        msgs.append(f"\n[bold green]✓ Apply complete.[/bold green]  [bold]→ Restart Claude Code.[/bold]")
        self.query_one("#upd-status", Static).update("\n".join(msgs))
        self._refresh_preview()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._refresh_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "upd-refresh":
            self._refresh_preview()
        elif bid == "upd-apply":
            self.action_apply()
        elif bid == "upd-restore":
            self.app.push_screen(RestoreScreen())


