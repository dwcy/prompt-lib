# -*- coding: utf-8 -*-
"""GlobalEnvScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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

class GlobalEnvScreen(Screen):
    """Browse every environment variable currently set on this machine."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    CSS = """
    GlobalEnvScreen { align: center middle; }
    #gv-card {
        width: 95%;
        height: 90%;
        padding: 1 2;
        background: $boost;
        border: round $primary;
    }
    #gv-search { margin: 0 0 1 0; }
    #gv-list { height: 1fr; }
    #gv-actions { height: 3; margin-top: 1; align-horizontal: center; }
    #gv-actions Button { margin: 0 1; }
    """

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Vertical(id="gv-card"):
            yield Static(
                "[bold bright_magenta]✦ All environment variables ✦[/bold bright_magenta]\n"
                "[dim]Snapshot of os.environ — type to filter by name or value.[/dim]"
            )
            yield Input(placeholder="Filter by name or value…", id="gv-search")
            yield Static("", id="gv-count")
            yield DataTable(id="gv-list")
            with Horizontal(id="gv-actions"):
                yield Button("Back", id="gv-back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#gv-list", DataTable)
        tbl.add_columns("Name", "Value")
        tbl.cursor_type = "row"
        self._all: list[tuple[str, str]] = sorted(os.environ.items())
        self._render_rows(self._all)

    def _render_rows(self, items: list[tuple[str, str]]) -> None:
        tbl = self.query_one("#gv-list", DataTable)
        tbl.clear()
        for name, value in items:
            shown = value if len(value) <= 200 else value[:200] + " …"
            # Escape so values containing `[...]` (e.g., PATH segments) aren't
            # parsed as Rich/Textual markup, which crashes DataTable rendering.
            tbl.add_row(escape_markup(name), escape_markup(shown))
        self.query_one("#gv-count", Static).update(
            f"[dim]{len(items)} of {len(self._all)} variables[/dim]"
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        q = (event.value or "").lower().strip()
        if not q:
            self._render_rows(self._all)
            return
        filtered = [(n, v) for n, v in self._all if q in n.lower() or q in v.lower()]
        self._render_rows(filtered)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gv-back":
            self.app.pop_screen()


