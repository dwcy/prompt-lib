# -*- coding: utf-8 -*-
"""LocalScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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
from cabal.local_setup import apply_group, build_plan
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
from cabal.views.folder_browser import GITIGNORE_BY_TEMPLATE
from cabal.widgets.env_panel import EnvPanel
from cabal.widgets.update_panel import UpdatePanel


class LocalScreen(Screen):
    """Set up .claude/ in another project."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
    ]

    def __init__(self) -> None:
        super().__init__()
        tpls = (
            sorted((GLOBAL_DIR / "project-templates").glob("*.md"))
            if (GLOBAL_DIR / "project-templates").exists()
            else []
        )
        self.template_options = [(p.stem, str(p)) for p in tpls]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Local project setup ✦[/bold bright_magenta]\n"
                "[dim]Pick a project folder and the actions to take.[/dim]",
                classes="panel",
            )
            with Horizontal():
                yield Label("Project path: ")
                yield Button("Browse…", id="loc-browse")
                yield Input(value=str(self.app.project_path()), id="loc-path")
            yield Checkbox(
                "Create .claude/ scaffolding (skills/, hooks/, settings.local.json)",
                value=True,
                id="loc-scaffold",
            )
            yield Static(
                "Creates .claude/skills/, .claude/hooks/, and settings.local.json with an empty permissions stub.\n"
                "Claude Code discovers project-local agents and skills from these dirs at session start (docs/architecture.md).\n"
                "[yellow]⚑ TODO: Edit .claude/settings.local.json → add allow[] entries for commands this project needs "
                "(e.g. npm, pytest, dotnet). Run Initialize env vars from the home screen first if MCP servers are needed.[/yellow]\n"
                "Test: ls .claude/ → skills/, hooks/, settings.local.json all present.",
                classes="help-text",
            )
            yield Checkbox(
                "Apply CLAUDE.md project template", value=False, id="loc-template"
            )
            yield Static(
                "Copies a starter CLAUDE.md from global/project-templates/ into the project root.\n"
                "Sets project conventions and stack hints that Claude reads at every session start (docs/rules-output-styles.md).\n"
                "Test: open a new Claude Code session in the project — the SessionStart hook detects CLAUDE.md and invokes @load-project.\n"
                "Review and customise the generated CLAUDE.md before committing it.",
                classes="help-text",
            )
            if self.template_options:
                yield Select(
                    self.template_options, id="loc-tpl-select", prompt="Pick template…"
                )
            yield Checkbox(
                "Add .gitignore matching the project template",
                value=False,
                id="loc-gitignore",
            )
            yield Static(
                "Writes a stack-specific .gitignore using the template picked above "
                "(python / dotnet / frontend / monorepo / unity / other).\n"
                "If a .gitignore already exists, the new entries are appended (with a header comment) instead of overwriting.\n"
                "Test: cat .gitignore → see the additions; `git status` should immediately ignore build dirs.",
                classes="help-text",
            )
            yield Checkbox(
                "Apply git repo-init template (hooks + .editorconfig + .gitattributes)",
                value=False,
                id="loc-git",
            )
            yield Static(
                "Copies global/git/.editorconfig and .gitattributes to the project root, and hook scripts to .git/hooks/.\n"
                "Requires git init to have been run in the project first.\n"
                "[yellow]⚑ TODO (Unix): run chmod +x .git/hooks/* after apply — Windows copies do not preserve execute bit.[/yellow]\n"
                "Test: ls .git/hooks/ → hook files present. Open a commit to confirm hooks fire.",
                classes="help-text",
            )
            yield Checkbox(
                "Initialize Spec Kit (specify init --here --integration claude)",
                value=False,
                id="loc-speckit",
            )
            yield Static(
                "Runs `specify init --here --integration claude` in the project to scaffold the Spec Kit workflow "
                "(.specify/, slash commands like /speckit-specify, /speckit-plan, /speckit-tasks).\n"
                "Requires the `specify` CLI — install it from the Tools screen (or run `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git`).\n"
                "If the target directory already contains .specify/, this passes `--force` to merge.\n"
                "Test: ls .specify/ → templates, scripts, memory all present. Open Claude Code → /speckit-specify should be listed.",
                classes="help-text",
            )
            yield Static("")
            yield DataTable(id="loc-preview")
            yield Static("")
            with Horizontal():
                yield Button("Refresh preview", id="loc-refresh")
                yield Button("Apply (Ctrl+A)", id="loc-apply", variant="success")
                yield Button("Back (Esc)", id="loc-back")
            yield Static("", id="loc-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        self._use: dict[str, bool] = {}
        self._child_keys: dict[str, list[str]] = {}
        tbl = self.query_one("#loc-preview", DataTable)
        tbl.cursor_type = "row"
        tbl.add_columns("Use", "Item", "State")
        self._refresh()

    @staticmethod
    def _box(symbol: str, color: str = "green") -> str:
        return rf"[{color}]\[{symbol}][/{color}]"

    def _parent_state(self, action: str) -> str:
        keys = self._child_keys.get(action, [])
        if not keys:
            return "empty"
        selected = sum(1 for k in keys if self._use.get(k))
        if selected == 0:
            return "none"
        if selected == len(keys):
            return "all"
        return "partial"

    def _parent_cell(self, action: str) -> str:
        return {
            "all": self._box("✓"),
            "none": self._box(" "),
            "partial": self._box("~"),
            "empty": self._box(" ", "dim"),
        }[self._parent_state(action)]

    def _leaf_cell(self, use_key: str) -> str:
        return self._box("✓") if self._use.get(use_key) else self._box(" ")

    def _project(self) -> Path:
        return Path(self.query_one("#loc-path", Input).value).expanduser()

    def _selected(self) -> dict:
        return {
            "scaffold": self.query_one("#loc-scaffold", Checkbox).value,
            "template": self.query_one("#loc-template", Checkbox).value,
            "gitignore": self.query_one("#loc-gitignore", Checkbox).value,
            "git": self.query_one("#loc-git", Checkbox).value,
            "speckit": self.query_one("#loc-speckit", Checkbox).value,
        }

    def _template_path(self) -> Path | None:
        if not self.template_options:
            return None
        try:
            sel = self.query_one("#loc-tpl-select", Select)
        except Exception:
            return None
        if not isinstance(sel.value, str):
            return None
        return Path(sel.value)

    def _open_browser(self) -> None:
        from cabal.views.folder_browser import FolderBrowserScreen

        raw = self.query_one("#loc-path", Input).value
        start = Path(raw).expanduser()
        if not start.is_dir():
            start = self.app.project_path()

        def _cb(path: Path | None) -> None:
            if path is not None:
                self.query_one("#loc-path", Input).value = str(path)
                self._refresh()

        self.app.push_screen(FolderBrowserScreen(start), _cb)

    def _plan(self, project: Path) -> list[dict]:
        sel = self._selected()
        tpl = self._template_path() if sel["template"] else None
        return build_plan(project, sel, tpl, self._template_path())

    def _refresh(self) -> None:
        if not hasattr(self, "_use"):
            self._use = {}
        tbl = self.query_one("#loc-preview", DataTable)
        tbl.clear()
        self._child_keys = {}
        project = self._project()

        if not project.exists() or not project.is_dir():
            tbl.add_row(
                self._box("✗", "red"),
                "[red]Path not a directory[/red]",
                f"[red]{project}[/red]",
            )
            return

        for g in self._plan(project):
            action = g["action"]
            selectable = [ch for ch in g["children"] if ch["op"] is not None]
            for ch in selectable:
                self._use.setdefault(ch["key"], True)
            self._child_keys[action] = [ch["key"] for ch in selectable]
            tbl.add_row(
                self._parent_cell(action),
                f"[bold]{g['label']}[/bold]",
                "",
                key=f"action::{action}",
            )
            for i, ch in enumerate(g["children"]):
                if ch["op"] is not None:
                    box = self._leaf_cell(ch["key"])
                    row_key = ch["key"]
                else:
                    box = self._box(" ", "dim")
                    row_key = f"noop::{action}::{i}"
                tbl.add_row(box, f"  └ {ch['label']}", ch["state"], key=row_key)

    def action_apply(self) -> None:
        project = self._project()
        if not project.is_dir():
            self.query_one("#loc-status", Static).update(
                f"[red]Not a directory:[/red] {project}"
            )
            return
        msgs: list[str] = []
        for g in self._plan(project):
            action = g["action"]
            chosen = [
                ch
                for ch in g["children"]
                if ch["op"] is not None and self._use.get(ch["key"])
            ]
            if not chosen:
                continue
            if action == "speckit":
                msgs.extend(self._apply_speckit(project))
            else:
                msgs.extend(apply_group(action, chosen, project))

        if not msgs:
            msgs.append("[yellow]Nothing selected.[/yellow]")
        self.query_one("#loc-status", Static).update("\n".join(msgs))
        self._refresh()

    def _apply_speckit(self, project: Path) -> list[str]:
        cmd = [
            "specify",
            "init",
            "--here",
            "--integration",
            "claude",
            "--ignore-agent-tools",
        ]
        if (project / ".specify").exists():
            cmd.append("--force")
        with self.app.suspend():
            r = subprocess.run(cmd, cwd=str(project))
        if r.returncode == 0:
            return [
                f"[green]✓ Spec Kit initialized[/green]  [dim]({' '.join(cmd)})[/dim]\n"
                "  Verify: ls .specify/ → templates/, scripts/, memory/ present."
            ]
        return [f"[red]✗ specify init failed (exit {r.returncode})[/red]"]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        if key.startswith("noop::"):
            return
        if key.startswith("action::"):
            action = key.split("::", 1)[1]
            kids = self._child_keys.get(action, [])
            if not kids:
                return
            turn_on = self._parent_state(action) != "all"
            for k in kids:
                self._use[k] = turn_on
        else:
            self._use[key] = not self._use.get(key, False)
        self._refresh()
        self.query_one("#loc-preview", DataTable).move_cursor(row=event.cursor_row)

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refresh()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._refresh()

    def on_select_changed(self, event: Select.Changed) -> None:
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "loc-back":
            self.app.pop_screen()
        elif bid == "loc-browse":
            self._open_browser()
        elif bid == "loc-refresh":
            self._refresh()
        elif bid == "loc-apply":
            self.action_apply()
