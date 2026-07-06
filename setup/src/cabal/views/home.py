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
from cabal.components import COMPONENTS, Component, ENV_DESCRIPTIONS, FileStatus
from cabal.diff_apply import (
    apply_statuses,
    backup_settings,
    diff_component,
    find_extras,
    has_deploy_drift,
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
from cabal.widgets.claude_doctor_panel import ClaudeDoctorPanel
from cabal.widgets.claude_sessions_panel import ClaudeSessionsPanel
from cabal.widgets.claude_stats_panel import ClaudeStatsPanel
from cabal.widgets.dashboard_panel import DashboardPanel
from cabal.widgets.logo import CabalLogo
from cabal.widgets.okf_panel import OkfPanel
from cabal.widgets.package_security_panel import PackageSecurityPanel
from cabal.widgets.update_panel import UpdatePanel


class HomeScreen(Screen):
    """Landing screen — banner + horizontal nav."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+s", "refresh_claude_stats", "Refresh stats"),
        Binding("ctrl+d", "refresh_dashboard", "Refresh dashboard"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader(show_clock=True)
        with VerticalScroll(id="home-scroll"):
            yield CabalLogo(id="banner", classes="centered")
            yield DashboardPanel(id="dashboard")
            yield ClaudeSessionsPanel(id="claude-sessions")
            with Vertical(id="claude-settings-panel", classes="home-section"):
                yield Static(
                    "[bold]Claude Settings (~/.claude)[/bold]",
                    id="claude-settings-title",
                    classes="home-section-title",
                )
                yield Static(
                    "[dim]Deploy, inspect, and tune ~/.claude — agents, hooks, skills, MCP servers, settings.[/dim]",
                    classes="home-section-desc",
                )
                with Horizontal(classes="ops-row"):
                    yield Button(
                        "Global File Configuration",
                        id="btn-op-update",
                        variant="default",
                    )
                    yield Button(
                        "StatusLine", id="btn-op-statusline", variant="default"
                    )
                with Horizontal(classes="ops-row"):
                    yield Button("Settings", id="btn-op-settings", variant="default")
                    yield Button("MCP Connectors", id="btn-op-mcp", variant="default")
                yield ClaudeStatsPanel(id="claude-stats")
                yield ClaudeDoctorPanel(id="claude-doctor")
                yield Static(
                    "[bold]Local Claude Settings[/bold]", classes="home-section-title"
                )
                with Horizontal(classes="ops-row"):
                    yield Button("Local Config", id="btn-op-local", variant="default")
            with Vertical(id="okf-analytics-panel", classes="home-section"):
                yield Static(
                    "[bold]OKF Analytics (docs/okf)[/bold]",
                    id="okf-analytics-title",
                    classes="home-section-title",
                )
                yield Static(
                    "[dim]OKF (Open Knowledge Format) turns agents, skills, hooks, "
                    "rules, and specs into a portable knowledge map for AI tools. "
                    "Use it to inspect how prompt-lib pieces connect, spot routing "
                    "overlap, export the OKF bundle, run Doctor checks, and open "
                    "the interactive graph viewer.[/dim]",
                    id="okf-analytics-desc",
                    classes="home-section-desc",
                )
                with Horizontal(classes="ops-row"):
                    yield Button(
                        "Knowledge Graph",
                        id="btn-op-knowledge",
                        variant="default",
                    )
                yield OkfPanel(id="okf-summary")
            with Vertical(id="services-panel", classes="home-section"):
                yield Static(
                    "[bold]Local Agent Services[/bold]",
                    id="services-title",
                    classes="home-section-title",
                )
                yield Static(
                    "[dim]See and run the local agent services — orchestrator, "
                    "a2a-bridge, and mcp-bus — from one place instead of "
                    "remembering CLI commands.[/dim]",
                    id="services-desc",
                    classes="home-section-desc",
                )
                with Horizontal(classes="ops-row"):
                    yield Button(
                        "Local Agent Services",
                        id="btn-op-services",
                        variant="default",
                    )
            with Vertical(id="pkgsec-panel", classes="home-section"):
                yield Static(
                    "[bold]Package Security Check[/bold]",
                    id="pkgsec-title",
                    classes="home-section-title",
                )
                yield Static(
                    "[dim]Scans this project's .NET, npm/frontend, and Python dependencies "
                    "for vulnerable, outdated, and deprecated packages. Runs automatically "
                    "when a project opens; fixes require your confirmation.[/dim]",
                    id="pkgsec-desc",
                    classes="home-section-desc",
                )
                with Horizontal(classes="ops-row"):
                    yield Button(
                        "Package Security Check",
                        id="btn-op-pkgsecurity",
                        variant="default",
                    )
                yield PackageSecurityPanel(id="pkgsec-summary")
            with Vertical(id="codex-settings-panel", classes="home-section"):
                yield Static(
                    "[bold]Codex Settings (~/.codex)[/bold]",
                    id="codex-settings-title",
                    classes="home-section-title",
                )
                yield Static(
                    "[dim]Deploy Codex-compatible skills to ~/.codex and scaffold .agents/ in projects.[/dim]",
                    classes="home-section-desc",
                )
                with Horizontal(classes="ops-row"):
                    yield Button(
                        "Global Codex Config",
                        id="btn-op-codex-update",
                        variant="default",
                    )
                    yield Button(
                        "Local Codex Config",
                        id="btn-op-codex-local",
                        variant="default",
                    )
                with Horizontal(classes="ops-row"):
                    yield Button(
                        "Conversion Diff",
                        id="btn-op-codex-conversion",
                        variant="default",
                    )
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self.query_one("#btn-op-update", Button).focus()
        self._apply_drift_markers()

    def action_readme(self) -> None:
        self.action_go("readme")

    def action_go(self, name: str) -> None:
        from cabal.views.readme import ReadmeScreen
        from cabal.views.git_config import GitConfigScreen

        if name == "readme":
            self.app.push_screen(ReadmeScreen())
        elif name == "git":
            self.app.push_screen(GitConfigScreen())

    def action_refresh_claude_stats(self) -> None:
        try:
            self.query_one("#claude-stats", ClaudeStatsPanel).refresh_stats()
        except Exception:
            pass

    def action_refresh_dashboard(self) -> None:
        try:
            self.query_one("#dashboard", DashboardPanel).refresh_dashboard()
        except Exception:
            pass

    def _apply_drift_markers(self) -> None:
        """Flag the deploy-target buttons yellow when repo and ~/.claude/ are out of sync."""
        try:
            drift = has_deploy_drift()
        except Exception:
            drift = False
        for bid, base in (
            ("btn-op-update", "Global File Configuration"),
            ("btn-op-local", "Local Config"),
        ):
            try:
                btn = self.query_one(f"#{bid}", Button)
            except Exception:
                continue
            label = Text(base)
            if drift:
                label.append("  ⚠ update available", style="yellow")
                btn.tooltip = (
                    "Repo has changes not yet deployed to ~/.claude — "
                    "run Global File Configuration to sync."
                )
            else:
                btn.tooltip = None
            btn.label = label
        try:
            from cabal.codex_setup.diff_apply import has_codex_deploy_drift

            codex_drift = has_codex_deploy_drift()
        except Exception:
            codex_drift = False
        try:
            btn = self.query_one("#btn-op-codex-update", Button)
            label = Text("Global Codex Config")
            if codex_drift:
                label.append("  ⚠ update available", style="yellow")
                btn.tooltip = "Repo has Codex assets not yet deployed to ~/.codex."
            else:
                btn.tooltip = None
            btn.label = label
        except Exception:
            pass

    def on_screen_resume(self) -> None:
        try:
            self.query_one("#dashboard", DashboardPanel).refresh_dashboard()
        except Exception:
            pass
        try:
            self.query_one("#claude-sessions", ClaudeSessionsPanel).refresh_sessions()
        except Exception:
            pass
        try:
            self.query_one("#claude-doctor", ClaudeDoctorPanel).refresh_doctor()
        except Exception:
            pass
        self._apply_drift_markers()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from cabal.views.update import UpdateScreen
        from cabal.views.mcp import McpScreen
        from cabal.views.local import LocalScreen
        from cabal.views.statusline import StatuslineScreen
        from cabal.views.knowledge import KnowledgeScreen
        from cabal.views.package_security import PackageSecurityScreen
        from cabal.views.services import ServicesScreen
        from cabal.views.settings import SettingsScreen
        from cabal.views.codex_update import CodexUpdateScreen
        from cabal.views.codex_local import CodexLocalScreen
        from cabal.views.codex_conversion import CodexConversionScreen

        bid = event.button.id or ""
        op_screens = {
            "btn-op-update": UpdateScreen,
            "btn-op-mcp": McpScreen,
            "btn-op-local": LocalScreen,
            "btn-op-statusline": StatuslineScreen,
            "btn-op-knowledge": KnowledgeScreen,
            "btn-op-services": ServicesScreen,
            "btn-op-pkgsecurity": PackageSecurityScreen,
            "btn-op-settings": SettingsScreen,
            "btn-op-codex-update": CodexUpdateScreen,
            "btn-op-codex-local": CodexLocalScreen,
            "btn-op-codex-conversion": CodexConversionScreen,
        }
        if bid == "btn-git":
            self.action_go("git")
        elif bid in op_screens:
            self.app.push_screen(op_screens[bid]())
