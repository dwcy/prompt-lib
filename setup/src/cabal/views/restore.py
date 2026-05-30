# -*- coding: utf-8 -*-
"""RestoreScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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
from cabal.widgets.env_panel import EnvPanel
from cabal.widgets.update_panel import UpdatePanel

class RestoreScreen(Screen):
    """Pick a settings.json backup and restore it."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Restore settings.json ✦[/bold bright_magenta]\n"
                f"[dim]From {TARGET}[/dim]",
                classes="panel",
            )
            self.baks = sorted(TARGET.glob("settings.json.bak*"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
            if not self.baks:
                yield Static("[yellow]No backups found.[/yellow]")
            else:
                opts = []
                for b in self.baks:
                    ts = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    opts.append(Option(f"{b.name}  ({ts}, {b.stat().st_size:,} bytes)", id=str(b)))
                yield OptionList(*opts, id="bak-list")
                yield Static("")
                with Horizontal():
                    yield Button("Restore selected", id="rst-apply", variant="warning")
                    yield Button("Back (Esc)", id="rst-back")
            yield Static("", id="rst-status", classes="panel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "rst-back":
            self.app.pop_screen()
        elif bid == "rst-apply":
            try:
                lst = self.query_one("#bak-list", OptionList)
            except Exception:
                return
            if lst.highlighted is None:
                self.query_one("#rst-status", Static).update("[yellow]Pick a backup first.[/yellow]")
                return
            opt = lst.get_option_at_index(lst.highlighted)
            backup = Path(opt.id)
            cur = TARGET / "settings.json"
            if cur.exists():
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.copy2(cur, TARGET / f"settings.json.bak.{ts}.pre-restore")
            shutil.copy2(backup, cur)
            self.query_one("#rst-status", Static).update(
                f"[green]✓ Restored from {backup.name}[/green]\n[bold]→ Restart Claude Code.[/bold]"
            )


