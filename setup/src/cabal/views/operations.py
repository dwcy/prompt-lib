# -*- coding: utf-8 -*-
"""OperationsScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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

class OperationsScreen(Screen):
    """Sub-menu for the heavier flows."""

    BINDINGS = [
        Binding("u", "go('update')", "Update"),
        Binding("m", "go('mcp')", "MCP"),
        Binding("d", "go('doctor')", "Doctor"),
        Binding("r", "go('restore')", "Restore"),
        Binding("l", "go('local')", "Local"),
        Binding("t", "go('tools')", "Tools"),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Operations ✦[/bold bright_magenta]\n"
                "[dim]Pick an action — letter shortcut or click.[/dim]",
                classes="panel",
            )
            with Horizontal(id="ops-nav"):
                yield Button("[U] Update", id="op-update", variant="primary")
                yield Button("[M] MCP", id="op-mcp", variant="primary")
                yield Button("[D] Doctor", id="op-doctor", variant="primary")
                yield Button("[R] Restore", id="op-restore", variant="primary")
                yield Button("[L] Local", id="op-local", variant="primary")
                yield Button("[T] Tools", id="op-tools", variant="primary")
                yield Button("Back (Esc)", id="op-back")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self.query_one("#op-update", Button).focus()

    def action_go(self, name: str) -> None:
        from cabal.views.update import UpdateScreen
        from cabal.views.mcp import McpScreen
        from cabal.views.doctor import DoctorScreen
        from cabal.views.restore import RestoreScreen
        from cabal.views.local import LocalScreen
        from cabal.views.tools import ToolsScreen
        target = {
            "update": UpdateScreen,
            "mcp": McpScreen,
            "doctor": DoctorScreen,
            "restore": RestoreScreen,
            "local": LocalScreen,
            "tools": ToolsScreen,
        }.get(name)
        if target:
            self.app.push_screen(target())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = (event.button.id or "").removeprefix("op-")
        if bid == "back":
            self.app.pop_screen()
        else:
            self.action_go(bid)


