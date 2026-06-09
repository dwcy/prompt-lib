# -*- coding: utf-8 -*-
"""DoctorScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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

class DoctorScreen(Screen):
    """Drift report — repo vs target."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("ctrl+r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Doctor — drift report ✦[/bold bright_magenta]\n"
                f"[dim]Comparing {GLOBAL_DIR} (repo) against {TARGET} (target).[/dim]\n\n"
                "[bold red]Repo only[/bold red]   In repo, not deployed yet. → Run [bold]Update[/bold].\n"
                "[bold yellow]Differs[/bold yellow]      In both, content mismatch. Repo wins on Update.\n"
                "[bold magenta]Target only[/bold magenta]  In ~/.claude/, not in repo. Stale or unsaved-promotion.",
                classes="panel",
            )
            yield Static("", id="doctor-summary")
            yield DataTable(id="drift", show_cursor=False)
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        tbl = self.query_one("#drift", DataTable)
        tbl.add_columns("Component", "Repo only", "Differs", "Target only", "Files")
        self._refresh()

    def action_refresh(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        tbl = self.query_one("#drift", DataTable)
        tbl.clear()
        any_issue = False
        for comp in COMPONENTS:
            if not comp.src_path.exists():
                continue
            statuses = diff_component(comp)
            repo_only = [str(s.rel) for s in statuses if s.state == "NEW"]
            differs = [str(s.rel) for s in statuses if s.state == "CHANGED"]
            target_only = [str(p) for p in find_extras(comp)]
            if repo_only or differs or target_only:
                any_issue = True
            parts = []
            for label, files, color in [("repo only", repo_only, "red"), ("differs", differs, "yellow"), ("target only", target_only, "magenta")]:
                if files:
                    shown = ", ".join(files[:3])
                    if len(files) > 3:
                        shown += f", … +{len(files) - 3}"
                    parts.append(f"[{color}]{label}:[/{color}] {shown}")
            files_col = " | ".join(parts) if parts else "[green]✓ in sync[/green]"
            tbl.add_row(
                comp.label,
                str(len(repo_only)) if repo_only else "·",
                str(len(differs)) if differs else "·",
                str(len(target_only)) if target_only else "·",
                files_col,
            )
        msg = "[yellow]⚠ Drift detected.[/yellow] Run Update to align." if any_issue else "[green]✓ Target matches repo.[/green]"
        self.query_one("#doctor-summary", Static).update(msg)


