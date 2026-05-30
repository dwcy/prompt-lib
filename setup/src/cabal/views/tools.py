# -*- coding: utf-8 -*-
"""ToolsScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

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
from cabal.env_detect import _dotnet_sdks, detect_env, find_env_vars
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

class ToolsScreen(Screen):
    """Install missing dependencies, grouped by category. Each group is its own panel."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    CSS = """
    ToolsScreen .tool-group {
        height: auto;
        padding: 1 2;
        margin: 0 2 1 2;
        background: $boost;
        border: round $accent;
    }
    ToolsScreen .tool-group-title {
        text-style: bold;
        color: #5FAFFF;
        margin: 0 0 1 0;
    }
    ToolsScreen .tool-row {
        layout: horizontal;
        height: 1;
        margin: 0;
    }
    ToolsScreen .tool-name { width: 18; }
    ToolsScreen .tool-state { width: 1fr; }
    ToolsScreen Button.tool-install,
    ToolsScreen Button.tool-install:hover,
    ToolsScreen Button.tool-install:focus {
        width: 11;
        min-width: 11;
        max-width: 11;
        height: 1;
        min-height: 1;
        max-height: 1;
        padding: 0;
        margin: 0;
        border: none;
        border-top: none;
        border-bottom: none;
        color: white;
        text-style: bold;
        content-align: center middle;
        tint: rgba(0,0,0,0);
    }
    ToolsScreen Button.tool-install        { background: #155E75; }
    ToolsScreen Button.tool-install:hover  { background: #1B7A94; }
    ToolsScreen Button.tool-install:focus  { background: #0E4A5C; }
    ToolsScreen Button.tool-install.-update         { background: #FB8C00; }
    ToolsScreen Button.tool-install.-update:hover   { background: #FFA726; }
    ToolsScreen Button.tool-install.-update:focus   { background: #EF6C00; }
    ToolsScreen Button.tool-install:disabled {
        background: $surface;
        color: $text-muted;
    }
    """

    @staticmethod
    def _sorted_keys(keys: list[str]) -> list[str]:
        """Order keys alphabetically by display label (case-insensitive)."""
        def _label(k: str) -> str:
            meta = _installer_for(k)
            return (meta[0] if meta else k).lower()
        return sorted(keys, key=_label)

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Tools ✦[/bold bright_magenta]\n"
                "[dim]Install missing dependencies. Each group is a panel; "
                "tools you already have are shown checked off.[/dim]",
                classes="panel",
            )
            for group_name, keys in ENV_TOOL_GROUPS:
                slug = re.sub(r"[^a-z0-9]+", "-", group_name.lower()).strip("-")
                with Vertical(classes="tool-group", id=f"tool-group-{slug}"):
                    yield Static(f"✦ {group_name}", classes="tool-group-title")
                    for key in self._sorted_keys(keys):
                        meta = _installer_for(key)
                        if meta is None:
                            continue
                        label, _fn = meta
                        with Horizontal(classes="tool-row"):
                            yield Static(f"[white]{label}[/]", classes="tool-name")
                            yield Static("", classes="tool-state", id=f"tool-state-{key}")
                            yield Button("Install", id=f"tool-install-{key}", classes="tool-install")
            yield Static("", id="tools-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def action_refresh(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self._installed_keys: set[str] = set()
        self._installed_details: dict[str, str] = {}
        for group in self.query(".tool-group"):
            group.loading = True
        # Single worker iterates groups sequentially, but renders each group's rows
        # immediately when ready (via call_from_thread). The UI updates after each
        # group, so panels clear one-by-one in declared order rather than all at once.
        self.run_worker(self._load_groups, thread=True, exclusive=True)

    def _load_groups(self) -> None:
        for group_name, keys in ENV_TOOL_GROUPS:
            slug = re.sub(r"[^a-z0-9]+", "-", group_name.lower()).strip("-")
            sorted_keys = self._sorted_keys(keys)
            try:
                env_subset = {k: _probe_key(k) for k in sorted_keys}
                if "dotnet" in sorted_keys:
                    env_subset["dotnet_sdks"] = _dotnet_sdks()
            except Exception as e:
                self.app.call_from_thread(self._group_error, slug, str(e))
                continue
            self.app.call_from_thread(self._apply_group, sorted_keys, env_subset, slug)
        # All groups rendered — now spawn the slower update check.
        self.app.call_from_thread(self._start_outdated_check)

    def _start_outdated_check(self) -> None:
        self.query_one("#tools-status", Static).update(
            "[dim italic]Checking for updates…[/]"
        )
        self.run_worker(self._load_outdated, thread=True, exclusive=False)

    def _load_outdated(self) -> None:
        try:
            outdated = _outdated_packages()
            env_value: object
            for key in VERSION_FLOORS:
                if key == "dotnet":
                    env_value = _dotnet_sdks()
                else:
                    env_value = _probe_key(key)
                if _below_floor(key, env_value):
                    outdated.add(key)
        except Exception as e:
            self.app.call_from_thread(
                self.query_one("#tools-status", Static).update,
                f"[red]Update check failed: {e}[/red]",
            )
            return
        self.app.call_from_thread(self._apply_outdated, outdated)

    def _group_error(self, slug: str, msg: str) -> None:
        self.query_one("#tools-status", Static).update(
            f"[red]Group {slug} failed: {msg}[/red]"
        )
        try:
            self.query_one(f"#tool-group-{slug}", Vertical).loading = False
        except Exception:
            pass

    def _apply_group(self, keys: list[str], env_subset: dict, slug: str) -> None:
        try:
            for key in keys:
                installed, detail = self._tool_state(key, env_subset)
                try:
                    state_w = self.query_one(f"#tool-state-{key}", Static)
                    btn = self.query_one(f"#tool-install-{key}", Button)
                except Exception:
                    continue  # widget missing — skip this key, don't trap the group
                if installed:
                    self._installed_keys.add(key)
                    self._installed_details[key] = detail
                    suffix = f" [dim]{detail}[/dim]" if detail else ""
                    state_w.update(
                        f"[bright_green]✓ installed[/bright_green]{suffix}  "
                        f"[dim](checking for updates…)[/dim]"
                    )
                    btn.display = False
                    btn.remove_class("-update")
                else:
                    state_w.update("[red]✗ not installed[/red]")
                    btn.display = True
                    btn.disabled = False
                    btn.label = "Install"
                    btn.remove_class("-update")
        finally:
            # Always clear loading, even if rendering raised partway through.
            try:
                self.query_one(f"#tool-group-{slug}", Vertical).loading = False
            except Exception:
                pass

    def _apply_outdated(self, outdated: set[str]) -> None:
        for key in list(self._installed_keys):
            state_w = self.query_one(f"#tool-state-{key}", Static)
            btn = self.query_one(f"#tool-install-{key}", Button)
            detail = self._installed_details.get(key, "")
            suffix = f" [dim]{detail}[/dim]" if detail else ""
            if key in outdated:
                state_w.update(f"[bright_yellow]⬇ update available[/bright_yellow]{suffix}")
                btn.display = True
                btn.disabled = False
                btn.label = "Update"
                btn.add_class("-update")
            else:
                state_w.update(f"[bright_green]✓ Latest[/bright_green]{suffix}")
                btn.display = False
                btn.remove_class("-update")

    def _tool_state(self, key: str, env: dict) -> tuple[bool, str]:
        """Return (installed, detail) — detail is the version string when known."""
        val = env.get(key)
        if isinstance(val, str) and val:
            # versioned probe (e.g. node → 'v22.16.0')
            return True, val
        return bool(val), ""

    _SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if not bid.startswith("tool-install-"):
            return
        key = bid.removeprefix("tool-install-")
        meta = _installer_for(key)
        if meta is None:
            return
        label, installer = meta
        btn = event.button
        self._start_spinner(btn)
        self.query_one("#tools-status", Static).update(
            f"[yellow]⏳ Installing {label}…[/yellow]"
        )
        self.run_worker(
            lambda: self._do_install(key, label, installer, btn),
            thread=True, exclusive=False,
        )

    def _start_spinner(self, button: Button) -> None:
        button.disabled = True
        state = {"frame": 0}
        def tick() -> None:
            state["frame"] = (state["frame"] + 1) % len(self._SPINNER_FRAMES)
            button.label = self._SPINNER_FRAMES[state["frame"]]
        button.label = self._SPINNER_FRAMES[0]
        state["timer"] = self.set_interval(0.08, tick)
        if not hasattr(self, "_spinners"):
            self._spinners = {}
        self._spinners[button.id] = state

    def _stop_spinner(self, button_id: str) -> None:
        state = getattr(self, "_spinners", {}).pop(button_id, None)
        if state and "timer" in state:
            state["timer"].stop()

    def _do_install(
        self,
        key: str,
        label: str,
        installer: Callable[[], tuple[bool, str]],
        button: Button,
    ) -> None:
        try:
            ok, msg = installer()
        except Exception as e:
            ok, msg = False, f"error: {e}"

        def _done() -> None:
            self._stop_spinner(button.id)
            mark = "[green bold]✓[/green bold]" if ok else "[red bold]✗[/red bold]"
            lines = msg.splitlines() if msg else []
            snippet = "\n".join(lines[-8:]) if lines else ""
            body = f"\n[dim]{snippet}[/dim]" if snippet else ""
            self.query_one("#tools-status", Static).update(
                f"{mark} {label} {'installed' if ok else 'failed'}{body}"
            )
            button.disabled = False
            button.label = "Install"
            self._refresh()
        self.app.call_from_thread(_done)


