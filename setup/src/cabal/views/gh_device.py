# -*- coding: utf-8 -*-
"""GhDeviceFlowScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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

class GhDeviceFlowScreen(ModalScreen):
    """Modal that drives a GitHub OAuth Device Authorization flow inside the wizard.

    Dismisses with the access token on success, or None on cancel/error/timeout.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    GhDeviceFlowScreen { align: center middle; }
    #gh-dialog {
        width: 70; height: auto; padding: 1 2; border: round #FF55A5;
        background: $panel;
    }
    #gh-code {
        content-align: center middle; padding: 1 0;
        text-style: bold; color: #FFB6C1;
    }
    #gh-url, #gh-instructions, #gh-status-line { content-align: center middle; padding: 0 0; }
    #gh-actions { align: center middle; padding-top: 1; height: 3; }
    #gh-actions Button { margin: 0 1; }
    """

    def __init__(self, device: dict) -> None:
        super().__init__()
        self._device = device
        self._cancelled = False

    def compose(self) -> ComposeResult:
        with Container(id="gh-dialog"):
            yield Static("[bold bright_magenta]Login with GitHub[/bold bright_magenta]", id="gh-instructions")
            yield Static("\nEnter this code in your browser:\n", id="gh-instructions")
            code = self._device.get("user_code", "????-????")
            yield Static(f"╔══════════════╗\n║  [bold]{code}[/bold]  ║\n╚══════════════╝", id="gh-code")
            url = self._device.get("verification_uri", "https://github.com/login/device")
            yield Static(f"\n[dim]Browser opened to[/dim] [cyan]{url}[/cyan]", id="gh-url")
            yield Static("\n[dim]Waiting for authorization…[/dim]", id="gh-status-line")
            with Horizontal(id="gh-actions"):
                yield Button("Cancel (Esc)", id="gh-cancel", variant="error")

    def on_mount(self) -> None:
        import webbrowser
        try:
            webbrowser.open(self._device.get("verification_uri", "https://github.com/login/device"))
        except Exception:
            pass
        self.run_worker(self._poll, thread=True, exclusive=True)

    def _poll(self) -> None:
        import time
        interval = int(self._device.get("interval", 5))
        expires_in = int(self._device.get("expires_in", 900))
        deadline = time.monotonic() + expires_in
        device_code = self._device.get("device_code", "")
        start = time.monotonic()

        def _tick() -> None:
            elapsed = int(time.monotonic() - start)
            try:
                self.query_one("#gh-status-line", Static).update(
                    f"[dim]Waiting for authorization… {elapsed}s[/dim]"
                )
            except Exception:
                pass

        self.app.call_from_thread(_tick)

        ok, token, msg = gh_device_poll(
            device_code, interval, deadline, lambda: self._cancelled,
        )

        def _finish() -> None:
            if ok:
                self.dismiss(token)
            else:
                try:
                    self.query_one("#gh-status-line", Static).update(f"[red]✗ {msg}[/red]")
                except Exception:
                    pass
                self.dismiss(None)

        self.app.call_from_thread(_finish)

    def action_cancel(self) -> None:
        self._cancelled = True
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gh-cancel":
            self.action_cancel()


