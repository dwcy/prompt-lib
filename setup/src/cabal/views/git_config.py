# -*- coding: utf-8 -*-
"""GitConfigScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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

class GitConfigScreen(Screen):
    """View and edit global git config — user.name and user.email."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    CSS = """
    GitConfigScreen { align: center middle; }
    #git-card {
        width: 70;
        height: auto;
        padding: 1 2;
        background: $boost;
        border: round $primary;
    }
    #git-card Label { margin: 1 0 0 0; color: #5FAFFF; text-style: bold; }
    #git-card Input { margin: 0 0 0 0; }
    #git-actions { height: 3; margin-top: 1; align-horizontal: center; }
    #git-actions Button { margin: 0 1; }
    #git-status { height: auto; margin: 1 0 0 0; }
    """

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Vertical(id="git-card"):
            yield Static(
                "[bold bright_magenta]✦ Git config ✦[/bold bright_magenta]\n"
                "[dim]Edits write to your global `~/.gitconfig` via `git config --global`.[/dim]"
            )
            yield Label("user.name")
            yield Input(id="git-name", placeholder="Your name (e.g. for commit authorship)")
            yield Label("user.email")
            yield Input(id="git-email", placeholder="you@example.com")
            with Horizontal(id="git-actions"):
                yield Button("Save", id="git-save", variant="primary")
                yield Button("Reload", id="git-reload", variant="default")
                yield Button("Back", id="git-back", variant="default")
            yield Static("", id="git-status")
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    def _git(self) -> str | None:
        return shutil.which("git")

    def _read(self, key: str) -> str | None:
        git = self._git()
        if not git:
            return None
        try:
            r = subprocess.run(
                [git, "config", "--global", key],
                capture_output=True, text=True, timeout=3, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        v = (r.stdout or "").strip()
        return v or None

    def _write(self, key: str, value: str) -> tuple[bool, str]:
        git = self._git()
        if not git:
            return False, "git not found"
        try:
            r = subprocess.run(
                [git, "config", "--global", key, value],
                capture_output=True, text=True, timeout=3, check=False,
            )
        except (OSError, subprocess.SubprocessError) as e:
            return False, str(e)
        return r.returncode == 0, (r.stderr or "").strip()

    def _load(self) -> None:
        if not self._git():
            self.query_one("#git-status", Static).update(
                "[red]✗ git not found on PATH — install git first[/red]"
            )
            return
        self.query_one("#git-name", Input).value = self._read("user.name") or ""
        self.query_one("#git-email", Input).value = self._read("user.email") or ""
        self.query_one("#git-status", Static).update(
            "[dim]Loaded current values from global config.[/dim]"
        )

    def _save(self) -> None:
        name = self.query_one("#git-name", Input).value.strip()
        email = self.query_one("#git-email", Input).value.strip()
        results: list[tuple[str, bool, str]] = []
        for key, value in (("user.name", name), ("user.email", email)):
            if value:
                ok, msg = self._write(key, value)
                results.append((key, ok, msg))
        if not results:
            self.query_one("#git-status", Static).update("[yellow]Nothing to save — both fields are empty.[/yellow]")
            return
        lines = []
        for key, ok, msg in results:
            mark = "[green]✓[/]" if ok else "[red]✗[/]"
            extra = f" [dim]{msg}[/dim]" if msg else ""
            lines.append(f"{mark} {key}{extra}")
        self.query_one("#git-status", Static).update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "git-back":
            self.app.pop_screen()
        elif bid == "git-save":
            self._save()
        elif bid == "git-reload":
            self._load()


