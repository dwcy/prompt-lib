# -*- coding: utf-8 -*-
"""EnvScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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
from cabal.env_profile import update_profile
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

_PATH_KEYS: frozenset[str] = frozenset({"PROJECTS_PATH", "TEMP_PATH"})


class EnvScreen(Screen):
    """Show env vars (values from system env) and apply via setx / shell rc + git config."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
    ]

    def __init__(self) -> None:
        super().__init__()
        defaults: dict[str, str] = (
            json.loads(ENV_FILE.read_text(encoding="utf-8"))
            if ENV_FILE.exists()
            else {}
        )
        self.data: dict[str, str] = {
            k: os.environ.get(k) or v for k, v in defaults.items()
        }

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Environment variables ✦[/bold bright_magenta]\n"
                "[dim]Values read from system environment. "
                "Apply (Ctrl+A) sets them via setx (Windows) or shell rc (Unix). "
                "Status icon: ✓ set in current shell, ✗ missing.[/dim]",
                classes="panel",
            )
            for key, val in self.data.items():
                shell_set = bool(os.environ.get(key))
                icon = "[green]✓[/green]" if shell_set else "[red]✗[/red]"
                is_path = key in _PATH_KEYS
                with Horizontal(classes="env-row"):
                    yield Static(f"[bold cyan]{key}[/bold cyan]", classes="env-name")
                    yield Static(icon, classes="env-icon")
                    if is_path:
                        yield Button(
                            "Browse…", id=f"browse-{key}", classes="env-browse"
                        )
                    yield Input(
                        value=str(val),
                        id=f"in-{key}",
                        placeholder="(empty)",
                        classes="env-value",
                    )
                desc = ENV_DESCRIPTIONS.get(key)
                if desc:
                    yield Static(desc, classes="help-text")
            yield Static("")
            with Horizontal(id="env-actions"):
                yield Button("Apply (Ctrl+A)", id="env-apply", variant="success")
                yield Button("Back (Esc)", id="env-back")
                yield Button("System env", id="env-allenv", variant="primary")
            yield Static("", id="env-status")
        yield Footer(show_command_palette=False)

    def _gather(self) -> dict[str, str]:
        out = {}
        for key in self.data.keys():
            inp = self.query_one(f"#in-{key}", Input)
            out[key] = inp.value
        return out

    def _open_browser(self, key: str) -> None:
        from cabal.views.folder_browser import FolderBrowserScreen

        raw = self.query_one(f"#in-{key}", Input).value
        start = Path(raw).expanduser() if raw else Path.home()
        if not start.is_dir():
            start = start.parent if start.parent.is_dir() else Path.home()

        def _cb(path: Path | None) -> None:
            if path is not None:
                self.query_one(f"#in-{key}", Input).value = str(path)

        self.app.push_screen(FolderBrowserScreen(start), _cb)

    def action_apply(self) -> None:
        data = self._gather()
        msgs = []
        non_empty = {k: v for k, v in data.items() if v.strip()}

        if platform.system() == "Windows":
            for k, v in non_empty.items():
                r = subprocess.run(["setx", k, v], capture_output=True, text=True)
                ok = r.returncode == 0
                msgs.append(
                    f"  {'[green]✓[/green]' if ok else '[red]✗[/red]'} setx {k}"
                )
        else:
            export_lines = [f"export {k}={repr(v)}" for k, v in non_empty.items()]
            for profile in ["~/.bashrc", "~/.zshrc", "~/.profile"]:
                update_profile(profile, list(non_empty.keys()), export_lines)
            msgs.append("[green]✓ Updated shell rc files[/green]")

        gle = data.get("GIT_LINE_ENDINGS", "").strip()
        if gle:
            ok, msg = apply_git_line_endings(gle)
            msgs.append(f"  {'[green]✓[/green]' if ok else '[red]✗[/red]'} {msg}")

        msgs.append(
            "\n[bold]→ Restart your terminal for changes to take effect.[/bold]"
        )
        self.query_one("#env-status", Static).update("\n".join(msgs))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "env-apply":
            self.action_apply()
        elif bid == "env-back":
            self.app.pop_screen()
        elif bid == "env-allenv":
            from cabal.views.global_env import GlobalEnvScreen

            self.app.push_screen(GlobalEnvScreen())
        elif bid.startswith("browse-"):
            self._open_browser(bid.removeprefix("browse-"))
