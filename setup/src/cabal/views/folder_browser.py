# -*- coding: utf-8 -*-
"""FolderBrowserScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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

class FolderBrowserScreen(ModalScreen):
    """Modal directory picker — navigate the filesystem tree and select a folder."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("backspace", "go_up", "Parent"),
    ]

    def __init__(self, start: Path) -> None:
        super().__init__()
        self._current = start.resolve() if start.is_dir() else start.parent.resolve()
        self._entries: list[Path] = []

    def compose(self) -> ComposeResult:
        with Container(id="browser-dialog"):
            yield Static("", id="browser-path")
            yield OptionList(id="browser-list")
            with Horizontal(id="browser-actions"):
                yield Button("Select  [bold]↵[/bold]", id="br-select", variant="success")
                yield Button("Parent  [bold]⌫[/bold]", id="br-up")
                yield Button("Cancel  [bold]Esc[/bold]", id="br-cancel", variant="error")

    def on_mount(self) -> None:
        self._populate()
        self.query_one("#browser-list", OptionList).focus()

    def _populate(self) -> None:
        lst = self.query_one("#browser-list", OptionList)
        lst.clear_options()
        self.query_one("#browser-path", Static).update(
            f"[bold cyan]  {self._current}[/bold cyan]"
        )
        at_root = self._current.parent == self._current
        if not at_root:
            lst.add_option(Option("  ..", id="__up__"))
        try:
            entries = sorted(
                [d for d in self._current.iterdir() if d.is_dir()],
                key=lambda p: p.name.lower(),
            )
        except PermissionError:
            entries = []
        self._entries = entries
        for i, d in enumerate(entries):
            lst.add_option(Option(f"  {d.name}", id=f"__dir_{i}__"))

    def action_go_up(self) -> None:
        if self._current.parent != self._current:
            self._current = self._current.parent
            self._populate()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option.id or ""
        if opt_id == "__up__":
            self.action_go_up()
        elif opt_id.startswith("__dir_"):
            idx = int(opt_id[6:-2])
            if 0 <= idx < len(self._entries):
                self._current = self._entries[idx]
                self._populate()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "br-select":
            self.dismiss(self._current)
        elif bid == "br-up":
            self.action_go_up()
        elif bid == "br-cancel":
            self.action_cancel()


GITIGNORE_BY_TEMPLATE: dict[str, str] = {
    "python": """\
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
.eggs/
# Virtualenvs
.venv/
venv/
env/
ENV/
# Tooling caches
.pytest_cache/
.mypy_cache/
.ruff_cache/
.tox/
.coverage
htmlcov/
# Notebooks
.ipynb_checkpoints/
# Editors / OS
.idea/
.vscode/
*.swp
.DS_Store
Thumbs.db
# Env
.env
.env.local
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
    "dotnet": """\
# .NET build outputs
bin/
obj/
out/
artifacts/
# Visual Studio / Rider
.vs/
.vshistory/
.idea/
*.user
*.suo
*.userprefs
*.userosscache
*.sln.docstates
# Symbols / coverage
*.pdb
*.opendb
TestResults/
coverage/
*.coverage
*.coverage.xml
# NuGet
*.nupkg
packages/
# Editor / OS
.vscode/
*.swp
.DS_Store
Thumbs.db
# Env
.env
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
    "frontend": """\
# Dependencies
node_modules/
.pnpm-store/
# Build / output
dist/
build/
out/
.next/
.nuxt/
.output/
.svelte-kit/
.vercel/
.netlify/
.astro/
.expo/
# Cache
.cache/
.parcel-cache/
.turbo/
.eslintcache
.stylelintcache
# Coverage / test
coverage/
playwright-report/
test-results/
# Logs
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
*.log
# Editor / OS
.vscode/
.idea/
*.swp
.DS_Store
Thumbs.db
# Env
.env
.env.*
!.env.example
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
    "monorepo": """\
# Monorepo orchestrators
.turbo/
.nx/
.rush/
# Common build outputs
node_modules/
dist/
build/
out/
.next/
.svelte-kit/
coverage/
# Cache
.cache/
.parcel-cache/
# Logs
*.log
npm-debug.log*
yarn-debug.log*
pnpm-debug.log*
# Editor / OS
.vscode/
.idea/
.DS_Store
Thumbs.db
# Env
.env
.env.*
!.env.example
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
    "unity": """\
# Unity-generated
[Ll]ibrary/
[Tt]emp/
[Oo]bj/
[Bb]uild/
[Bb]uilds/
[Ll]ogs/
[Uu]ser[Ss]ettings/
[Mm]emoryCaptures/
[Rr]ecordings/
# Generated solution / project files
*.csproj
*.unityproj
*.sln
*.suo
*.user
*.userprefs
*.pidb
*.booproj
*.svd
*.pdb
*.mdb
*.opendb
*.VC.db
# Build artifacts
ExportedObj/
.consulo/
*.apk
*.aab
*.unitypackage
crashlytics-build.properties
# OS / editor
.vscode/
.idea/
.DS_Store
Thumbs.db
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
    "other": """\
# OS
.DS_Store
Thumbs.db
ehthumbs.db
desktop.ini
# Editor
.vscode/
.idea/
*.swp
*.swo
*~
# Logs
*.log
# Env
.env
.env.local
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
}


