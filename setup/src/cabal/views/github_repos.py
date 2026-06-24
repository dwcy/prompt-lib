# -*- coding: utf-8 -*-
"""GitHubReposScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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

from cabal import gh_accounts
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


class GitHubReposScreen(Screen):
    """List repos owned by the gh-authenticated user via `gh repo list --json`."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("c", "clone", "Clone"),
    ]

    CSS = """
    GitHubReposScreen { align: center middle; }
    #gh-repos-card {
        width: 95%;
        height: 90%;
        padding: 1 2;
        background: $boost;
        border: round #CC006B;
    }
    #gh-repos-status { height: auto; margin: 0 0 1 0; }
    #gh-repos-list { height: 1fr; }
    #gh-repos-actions { height: 3; margin-top: 1; align-horizontal: center; }
    #gh-repos-actions Button { margin: 0 1; }
    """

    def __init__(self, on_clone_done: Callable[[Path], None] | None = None) -> None:
        super().__init__()
        self._on_clone_done = on_clone_done

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Vertical(id="gh-repos-card"):
            yield Static(
                "[bold bright_magenta]✦ GitHub repos ✦[/bold bright_magenta]\n"
                "[dim]Lists repos owned by your gh-authenticated account.[/dim]"
            )
            yield Static("", id="gh-repos-status")
            yield DataTable(id="gh-repos-list")
            with Horizontal(id="gh-repos-actions"):
                yield Button("Clone selected", id="gh-repos-clone", variant="success")
                yield Button("Login with GitHub", id="gh-repos-login", variant="primary")
                yield Button("Accounts", id="gh-repos-accounts", variant="primary")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._repos: list[dict] = []
        tbl = self.query_one("#gh-repos-list", DataTable)
        tbl.add_columns("Name", "Visibility", "Updated", "Description")
        tbl.cursor_type = "row"
        self.query_one("#gh-repos-login", Button).display = False
        self.action_refresh()

    def action_refresh(self) -> None:
        self.query_one("#gh-repos-status", Static).update(
            "[yellow]⏳ Fetching repos via gh CLI…[/yellow]"
        )
        self.run_worker(self._fetch, thread=True, exclusive=True)

    def _fetch(self) -> None:
        gh = shutil.which("gh")
        if not gh:
            self.app.call_from_thread(
                self._set_error, "gh not found on PATH — install GitHub CLI first"
            )
            return
        token_r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if token_r.returncode != 0 or not token_r.stdout.strip():
            self.app.call_from_thread(self._set_logged_out)
            return
        try:
            repos = self._gh_repos()
        except Exception as e:
            self.app.call_from_thread(self._set_error, str(e))
            return
        self.app.call_from_thread(self._set_repos, repos)

    def _gh_repos(self) -> list[dict]:
        gh = shutil.which("gh")
        if not gh:
            raise RuntimeError("gh not found on PATH — install GitHub CLI first")
        r = subprocess.run(
            [
                gh,
                "repo",
                "list",
                "--limit",
                "200",
                "--json",
                "name,nameWithOwner,description,visibility,updatedAt,url",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if r.returncode != 0:
            err = (r.stderr or "").strip()
            raise RuntimeError(err or f"gh repo list failed (exit {r.returncode})")
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"could not parse gh output: {e}") from None
        return data if isinstance(data, list) else []

    def _set_error(self, message: str) -> None:
        self.query_one("#gh-repos-status", Static).update(f"[red]✗ {message}[/red]")

    def _set_logged_out(self) -> None:
        self._repos = []
        self.query_one("#gh-repos-list", DataTable).clear()
        self.query_one("#gh-repos-login", Button).display = True
        self.query_one("#gh-repos-status", Static).update(
            "[yellow]⚠ Not logged in to GitHub — click Login with GitHub to authenticate.[/yellow]"
        )

    def _set_repos(self, repos: list[dict]) -> None:
        self._repos = repos
        self.query_one("#gh-repos-login", Button).display = False
        tbl = self.query_one("#gh-repos-list", DataTable)
        tbl.clear()
        for repo in repos:
            updated = (repo.get("updatedAt") or "")[:10]  # ISO YYYY-MM-DD
            vis = (repo.get("visibility") or "").lower()
            # vis is one of "public" / "private" / "internal" — safe for markup.
            vis_styled = Text.from_markup(
                f"[red]{vis}[/red]"
                if vis == "private"
                else f"[yellow]{vis}[/yellow]"
                if vis == "internal"
                else f"[green]{vis}[/green]"
            )
            desc = (repo.get("description") or "")[:80]
            tbl.add_row(
                escape_markup(repo.get("name", "")),
                vis_styled,
                updated,
                escape_markup(desc),
            )
        self.query_one("#gh-repos-status", Static).update(
            f"[green]✓[/green] {len(repos)} repos loaded"
        )

    def _open_accounts(self) -> None:
        from cabal.views.gh_accounts_modal import GhAccountsModal

        def _done(changed: bool | None) -> None:
            if changed:
                self.action_refresh()

        self.app.push_screen(GhAccountsModal(), _done)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "gh-repos-back":
            self.app.pop_screen()
        elif bid == "gh-repos-refresh":
            self.action_refresh()
        elif bid == "gh-repos-login":
            self._start_login()
        elif bid == "gh-repos-clone":
            self.action_clone()
        elif bid == "gh-repos-accounts":
            self._open_accounts()

    def action_clone(self) -> None:
        from cabal.views.clone_repo import CloneRepoScreen

        tbl = self.query_one("#gh-repos-list", DataTable)
        row = tbl.cursor_row
        if row is None or not (0 <= row < len(self._repos)):
            self.query_one("#gh-repos-status", Static).update(
                "[yellow]Select a repo row first, then Clone.[/yellow]"
            )
            return
        repo = self._repos[row]
        name_with_owner = repo.get("nameWithOwner") or repo.get("name", "")

        def _cb(path: Path | None) -> None:
            if path is not None and self._on_clone_done is not None:
                self._on_clone_done(path)

        self.app.push_screen(CloneRepoScreen(name_with_owner, repo.get("name", "")), _cb)

    def _start_login(self) -> None:
        self.query_one("#gh-repos-status", Static).update(
            "[dim]Starting GitHub device flow…[/dim]"
        )

        def _start() -> None:
            from cabal.views.gh_device import GhDeviceFlowScreen

            device = gh_device_init(["repo", "read:org"])

            def _push() -> None:
                if device is None:
                    self.query_one("#gh-repos-status", Static).update(
                        "[red]Could not reach github.com — check your connection[/red]"
                    )
                    return
                self.app.push_screen(GhDeviceFlowScreen(device), self._on_login)

            self.app.call_from_thread(_push)

        self.run_worker(_start, thread=True, exclusive=False)

    def _on_login(self, token: str | None) -> None:
        if not token:
            self.query_one("#gh-repos-status", Static).update("[yellow]Login cancelled[/yellow]")
            return
        self.query_one("#gh-repos-status", Static).update(
            "[dim]Registering account with gh…[/dim]"
        )

        def register() -> None:
            ok, msg = gh_accounts.add_account_with_token(token)
            self.app.call_from_thread(self._after_login_register, ok, msg)

        self.run_worker(register, thread=True, exclusive=True)

    def _after_login_register(self, ok: bool, msg: str) -> None:
        if ok:
            self.action_refresh()
        else:
            self.query_one("#gh-repos-status", Static).update(f"[red]✗ {msg}[/red]")
