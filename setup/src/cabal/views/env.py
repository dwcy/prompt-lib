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
_GH_TOKEN_KEYS: frozenset[str] = frozenset({"GITHUB_PERSONAL_ACCESS_TOKEN"})


class EnvScreen(Screen):
    """Show env vars (values from system env) and apply via setx / shell rc + git config."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
    ]

    def __init__(self) -> None:
        super().__init__()
        keys = (
            list(json.loads(ENV_FILE.read_text(encoding="utf-8")).keys())
            if ENV_FILE.exists()
            else []
        )
        self.data: dict[str, str] = {k: os.environ.get(k, "") for k in keys}

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
                    if key in _GH_TOKEN_KEYS:
                        yield Button(
                            "Fetch via gh", id=f"gh-fetch-{key}", classes="env-browse"
                        )
                        yield Button(
                            "Accounts", id=f"gh-accounts-{key}", classes="env-browse"
                        )
                        yield Button(
                            "Login with GitHub",
                            id=f"gh-login-{key}",
                            classes="env-browse",
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
                if key in _GH_TOKEN_KEYS:
                    yield Static("", id=f"gh-status-{key}", classes="help-text")
            yield Static("")
            with Horizontal(id="env-actions"):
                yield Button("Apply (Ctrl+A)", id="env-apply", variant="success")
                yield Button("Back (Esc)", id="env-back")
            yield Static("", id="env-status")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        for key in _GH_TOKEN_KEYS:
            if key in self.data:
                self.run_worker(
                    lambda k=key: self._check_gh_auth(k),
                    thread=True,
                    exclusive=False,
                )

    def _check_gh_auth(self, key: str) -> None:
        logged_in = False
        if not shutil.which("gh"):
            label = "[dim]gh CLI not installed — cannot fetch token[/dim]"
        else:
            # Use `gh auth token` as the source of truth — `gh auth status` can return
            # non-zero even when a valid token exists (scope/keychain quirks on Windows).
            token_r = subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True
            )
            if token_r.returncode == 0 and token_r.stdout.strip():
                logged_in = True
                # Also pull account info from auth status for display (best-effort)
                status_r = subprocess.run(
                    ["gh", "auth", "status"], capture_output=True, text=True
                )
                info = (
                    (status_r.stdout or status_r.stderr or "").strip().splitlines()[0]
                    if (status_r.stdout or status_r.stderr).strip()
                    else ""
                )
                label = f"[green]✓ gh: logged in[/green] [dim]{info}[/dim]"
            else:
                label = "[yellow]⚠ gh: not logged in — click Login with GitHub to authenticate[/yellow]"

        def _apply() -> None:
            try:
                self.query_one(f"#gh-status-{key}", Static).update(label)
            except Exception:
                pass

        self.app.call_from_thread(_apply)

    def _on_gh_token(self, key: str, token: str | None) -> None:
        """Callback when GhDeviceFlowScreen dismisses. Populates input on success."""
        status_widget = self.query_one("#env-status", Static)
        if not token:
            status_widget.update("[yellow]Login cancelled[/yellow]")
            return
        self.query_one(f"#in-{key}", Input).value = token
        try:
            self.query_one(f"#gh-status-{key}", Static).update(
                "[green]✓ gh: logged in (via wizard)[/green]"
            )
        except Exception:
            pass
        status_widget.update("[green]✓ Logged in — Apply (Ctrl+A) to persist[/green]")

    def _gather(self) -> dict[str, str]:
        out = {}
        for key in self.data.keys():
            inp = self.query_one(f"#in-{key}", Input)
            out[key] = inp.value
        return out

    def _fetch_gh_token(self, key: str) -> None:
        status_widget = self.query_one("#env-status", Static)
        status_widget.update("[dim]Contacting gh CLI…[/dim]")

        def _do() -> None:
            ok, token, msg = gh_fetch_token()

            def _apply() -> None:
                if ok:
                    self.query_one(f"#in-{key}", Input).value = token
                    status_widget.update(f"[green]✓ {msg}[/green]")
                else:
                    status_widget.update(f"[yellow]{msg}[/yellow]")

            self.app.call_from_thread(_apply)

        self.run_worker(_do, thread=True, exclusive=False)

    def _open_gh_accounts(self, key: str) -> None:
        from cabal.views.gh_accounts_modal import GhAccountsModal

        def _done(changed: bool | None) -> None:
            if not changed:
                return
            self.run_worker(
                lambda k=key: self._check_gh_auth(k), thread=True, exclusive=False
            )
            for panel in self.app.query(EnvPanel):
                panel.refresh_env()

        self.app.push_screen(GhAccountsModal(), _done)

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
        elif bid.startswith("browse-"):
            self._open_browser(bid.removeprefix("browse-"))
        elif bid.startswith("gh-fetch-"):
            self._fetch_gh_token(bid.removeprefix("gh-fetch-"))
        elif bid.startswith("gh-accounts-"):
            self._open_gh_accounts(bid.removeprefix("gh-accounts-"))
        elif bid.startswith("gh-login-"):
            key = bid.removeprefix("gh-login-")
            self.query_one("#env-status", Static).update(
                "[dim]Starting GitHub device flow…[/dim]"
            )

            def _start(k=key) -> None:
                from cabal.views.gh_device import GhDeviceFlowScreen

                device = gh_device_init(["repo", "read:org"])

                def _push() -> None:
                    if device is None:
                        self.query_one("#env-status", Static).update(
                            "[red]Could not reach github.com — check your connection[/red]"
                        )
                        return
                    self.app.push_screen(
                        GhDeviceFlowScreen(device),
                        lambda token: self._on_gh_token(k, token),
                    )

                self.app.call_from_thread(_push)

            self.run_worker(_start, thread=True, exclusive=False)
