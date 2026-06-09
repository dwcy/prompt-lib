# -*- coding: utf-8 -*-
"""HomeScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
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
from cabal.banner import HexBanner, render_banner, subtitle_bar
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
from cabal.widgets.claude_stats_panel import ClaudeStatsPanel
from cabal.widgets.env_panel import EnvPanel
from cabal.widgets.update_panel import UpdatePanel


class HomeScreen(Screen):
    """Landing screen — banner + horizontal nav."""

    BINDINGS = [
        Binding("ctrl+s", "refresh_claude_stats", "Refresh stats"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader(show_clock=True)
        with VerticalScroll(id="home-scroll"):
            yield HexBanner(id="banner", classes="centered", show_subtitle=False)
            yield subtitle_bar()
            yield EnvPanel(id="env-summary")
            with Vertical(classes="home-section"):
                yield Static(
                    "[bold]Claude Settings[/bold]", classes="home-section-title"
                )
                yield Static(
                    "[dim]Deploy and tune the files in ~/.claude — agents, hooks, skills, MCP servers, settings.[/dim]",
                    classes="home-section-desc",
                )
                with Horizontal(classes="ops-row"):
                    yield Button(
                        "[C] Global Claude file Config",
                        id="btn-op-update",
                        variant="default",
                    )
                    yield Button("[M] Global MCPs", id="btn-op-mcp", variant="default")
                    yield Button(
                        "[T] Statusline", id="btn-op-statusline", variant="default"
                    )
                yield ClaudeStatsPanel(id="claude-stats")
                yield Static(
                    "[bold]Local Claude Settings[/bold]", classes="home-section-title"
                )
                with Horizontal(classes="ops-row"):
                    yield Button("[D] Doctor", id="btn-op-doctor", variant="default")
                    yield Button(
                        "[N] Local MCP", id="btn-op-local-mcp", variant="default"
                    )
                    yield Button(
                        "[L] Local Config", id="btn-op-local", variant="default"
                    )
            with Vertical(classes="home-section"):
                yield Static("[bold]Project[/bold]", classes="home-section-title")
                with Horizontal(classes="ops-row"):
                    yield Button(
                        "[I] Init new project", id="btn-op-init", variant="primary"
                    )
                    yield Button(
                        "[O] Open existing project",
                        id="btn-op-open-project",
                        variant="primary",
                    )
        with Horizontal(id="home-bottom"):
            yield Button("[E] Env vars", id="btn-env", variant="primary")
            yield Button("[G] Git config", id="btn-git", variant="primary")
            yield Button("[H] GitHub", id="btn-github", variant="primary")
            yield Button("[V] All env", id="btn-allenv", variant="primary")
            yield Static("", classes="home-spacer")
            yield Button("[Q] Quit", id="btn-quit", variant="error")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self.query_one("#btn-env", Button).focus()

    def action_readme(self) -> None:
        self.action_go("readme")

    def action_go(self, name: str) -> None:
        from cabal.views.readme import ReadmeScreen
        from cabal.views.env import EnvScreen
        from cabal.views.git_config import GitConfigScreen
        from cabal.views.github_repos import GitHubReposScreen
        from cabal.views.global_env import GlobalEnvScreen

        if name == "readme":
            self.app.push_screen(ReadmeScreen())
        elif name == "env":
            self.app.push_screen(EnvScreen())
        elif name == "git":
            self.app.push_screen(GitConfigScreen())
        elif name == "github":
            self.app.push_screen(GitHubReposScreen())
        elif name == "allenv":
            self.app.push_screen(GlobalEnvScreen())

    def action_init_project(self) -> None:
        from cabal.views.init_project import InitProjectScreen

        self.app.push_screen(InitProjectScreen(on_created=self._project_changed))

    def action_open_project(self) -> None:
        from cabal.views.folder_browser import FolderBrowserScreen

        self.app.push_screen(FolderBrowserScreen(Path.cwd()), self._after_folder_picked)

    def action_refresh_claude_stats(self) -> None:
        try:
            self.query_one("#claude-stats", ClaudeStatsPanel).refresh_stats()
        except Exception:
            pass

    def _after_folder_picked(self, path: Path | None) -> None:
        if path is None:
            return
        self._project_changed(path)

    def _project_changed(self, path: Path) -> None:
        self.app.selected_project = path
        self._refresh_env_panel()

    def _refresh_env_panel(self) -> None:
        try:
            self.query_one("#env-summary", EnvPanel).refresh_project()
        except Exception:
            pass

    def on_screen_resume(self) -> None:
        self._refresh_env_panel()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from cabal.views.update import UpdateScreen
        from cabal.views.mcp import McpScreen
        from cabal.views.project_mcp import ProjectMcpScreen
        from cabal.views.doctor import DoctorScreen
        from cabal.views.local import LocalScreen
        from cabal.views.tools import ToolsScreen
        from cabal.views.statusline import StatuslineScreen

        bid = event.button.id or ""
        op_screens = {
            "btn-op-update": UpdateScreen,
            "btn-op-mcp": McpScreen,
            "btn-op-doctor": DoctorScreen,
            "btn-op-local": LocalScreen,
            "btn-op-tools": ToolsScreen,
            "btn-op-statusline": StatuslineScreen,
        }
        if bid == "btn-env":
            self.action_go("env")
        elif bid == "btn-git":
            self.action_go("git")
        elif bid == "btn-github":
            self.action_go("github")
        elif bid == "btn-allenv":
            self.action_go("allenv")
        elif bid == "btn-quit":
            self.app.exit()
        elif bid == "btn-op-init":
            self.action_init_project()
        elif bid == "btn-op-open-project":
            self.action_open_project()
        elif bid == "btn-op-local-mcp":
            self.app.push_screen(ProjectMcpScreen(target_dir=self.app.project_path()))
        elif bid in op_screens:
            self.app.push_screen(op_screens[bid]())
