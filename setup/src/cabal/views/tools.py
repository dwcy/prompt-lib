# > 400 LoC justified: required inline Textual CSS for grouped install buttons + multi-stage flow (group probe -> outdated check -> install worker -> per-row refresh) tightly coupled to ToolsScreen widget state.
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
import webbrowser
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
    _tool_unavailable_reason,
)
from cabal.tool_catalog import (
    SourceStatus,
    get_tool_definition,
    redact_secret_text,
)
from cabal.installers.runtime_backups import backup_before_install
from cabal.installers.versions import version_options_for
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
        border: round #CC006B;
    }
    ToolsScreen .tool-group-title {
        text-style: bold;
        color: #5FAFFF;
        margin: 0 0 1 0;
    }
    ToolsScreen .tool-row {
        layout: horizontal;
        height: auto;
        align: left middle;
        margin: 0 0 1 0;
    }
    ToolsScreen .tool-name { width: 22; }
    ToolsScreen .tool-state { width: 1fr; }
    ToolsScreen Select.tool-version {
        width: 28;
        max-width: 28;
        height: 1;
        margin: 0 1 0 0;
    }
    /* Compact Select drops the border; a background keeps it visible on one line. */
    ToolsScreen Select.tool-version > SelectCurrent {
        background: #2E3250;
        padding: 0 1;
    }
    ToolsScreen Select.tool-version:focus > SelectCurrent {
        background: #3C4170;
    }
    ToolsScreen Select.tool-version > SelectCurrent #label {
        color: white;
    }
    ToolsScreen Button.tool-source,
    ToolsScreen Button.tool-source:hover,
    ToolsScreen Button.tool-source:focus {
        width: 12;
        min-width: 12;
        max-width: 12;
        height: 1;
        min-height: 1;
        max-height: 1;
        padding: 0;
        margin: 0 1 0 0;
        border: none;
        color: white;
        text-style: bold;
        background: #355E3B;
        content-align: center middle;
    }
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

        return list(keys)

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
                        definition = get_tool_definition(key)
                        unavailable = _tool_unavailable_reason(key) is not None
                        display_label = self._display_label(label, definition)
                        with Horizontal(classes="tool-row", id=f"tool-row-{key}"):
                            name = Static(
                                display_label, classes="tool-name", id=f"tool-name-{key}"
                            )
                            if definition is not None and definition.description:
                                name.tooltip = redact_secret_text(definition.description)
                            yield name
                            yield Static(
                                "", classes="tool-state", id=f"tool-state-{key}"
                            )
                            if definition is not None and definition.version_provider:
                                version_result = version_options_for(
                                    definition.version_provider
                                )
                                options = [
                                    (option.label, option.version)
                                    for option in version_result.options
                                ]
                                yield Select(
                                    options
                                    or [("Version metadata unavailable", "unavailable")],
                                    id=f"tool-version-{key}",
                                    classes="tool-version",
                                    prompt="Version...",
                                    compact=True,
                                )
                            yield Button(
                                "N/A" if unavailable else "Install",
                                id=f"tool-install-{key}",
                                classes="tool-install",
                                disabled=unavailable,
                            )
                            # "Read more" / Source always last, after install/update.
                            if definition is not None:
                                source_disabled = not bool(definition.source_url)
                                source_label = (
                                    "Read more"
                                    if definition.source_status == SourceStatus.VERIFIED
                                    else "Source req"
                                )
                                yield Button(
                                    source_label,
                                    id=f"tool-source-{key}",
                                    classes="tool-source",
                                    disabled=source_disabled,
                                )
            yield Static("", id="tools-status", classes="panel")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._refresh()

    @staticmethod
    def _display_label(label: str, definition: object | None) -> str:
        badges = getattr(definition, "badges", ()) if definition is not None else ()
        if not badges:
            return f"[white]{escape_markup(label)}[/]"
        rendered = " ".join(
            f"[bright_green]{escape_markup(f'[{badge}]')}[/]" for badge in badges
        )
        return f"[white]{escape_markup(label)}[/] {rendered}"

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

    def _refresh_one(self, key: str) -> None:
        """Re-probe a single tool row + re-run the outdated check.

        Used after a per-tool install/update so the rest of the view doesn't
        flash loading state and the #tools-status install result stays visible.
        """
        self.run_worker(
            lambda: self._reload_one_worker(key),
            thread=True,
            exclusive=False,
        )

    def _reload_one_worker(self, key: str) -> None:
        try:
            env_subset: dict = {key: _probe_key(key)}
            if key == "dotnet":
                env_subset["dotnet_sdks"] = _dotnet_sdks()
        except Exception:
            return
        self.app.call_from_thread(self._apply_one_row, key, env_subset)
        try:
            outdated = _outdated_packages()
            for k in VERSION_FLOORS:
                env_val = _dotnet_sdks() if k == "dotnet" else _probe_key(k)
                if _below_floor(k, env_val):
                    outdated.add(k)
        except Exception:
            outdated = set()
        self.app.call_from_thread(self._apply_outdated, outdated)

    def _apply_one_row(self, key: str, env_subset: dict) -> None:
        try:
            state_w = self.query_one(f"#tool-state-{key}", Static)
            btn = self.query_one(f"#tool-install-{key}", Button)
        except Exception:
            return
        installed, detail = self._tool_state(key, env_subset)
        self._apply_row_state(key, state_w, btn, installed, detail)

    def _apply_row_state(
        self,
        key: str,
        state_w: Static,
        btn: Button,
        installed: bool,
        detail: str,
    ) -> None:
        reason = _tool_unavailable_reason(key)
        if reason:
            self._apply_unavailable_row(key, state_w, btn, reason)
        elif installed:
            self._installed_keys.add(key)
            self._installed_details[key] = detail
            suffix = f" [dim]{escape_markup(redact_secret_text(detail))}[/dim]" if detail else ""
            state_w.update(
                f"[bright_green]✓ installed[/bright_green]{suffix}  "
                f"[dim](checking for updates…)[/dim]"
            )
            btn.display = False
            btn.remove_class("-update")
        else:
            self._installed_keys.discard(key)
            self._installed_details.pop(key, None)
            state_w.update("[red]✗ not installed[/red]")
            btn.display = True
            definition = get_tool_definition(key)
            btn.disabled = bool(definition and not definition.automation_enabled)
            btn.label = "Install"
            btn.remove_class("-update")

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
                self._apply_row_state(key, state_w, btn, installed, detail)
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
            suffix = f" [dim]{escape_markup(redact_secret_text(detail))}[/dim]" if detail else ""
            if key in outdated:
                state_w.update(
                    f"[bright_yellow]⬇ update available[/bright_yellow]{suffix}"
                )
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

    def _apply_unavailable_row(
        self, key: str, state_w: Static, btn: Button, reason: str
    ) -> None:
        self._installed_keys.discard(key)
        self._installed_details.pop(key, None)
        state_w.update(
            f"[bright_yellow]not available[/bright_yellow] "
            f"[dim]{escape_markup(redact_secret_text(reason))}[/dim]"
        )
        btn.display = True
        btn.disabled = True
        definition = get_tool_definition(key)
        btn.label = "Source" if definition and definition.source_status == SourceStatus.MANUAL_REQUIRED else "N/A"
        btn.remove_class("-update")

    _SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("tool-source-"):
            key = bid.removeprefix("tool-source-")
            definition = get_tool_definition(key)
            if definition is None:
                return
            if definition.source_url:
                self.query_one("#tools-status", Static).update(
                    f"[cyan]{escape_markup(definition.label)} source:[/cyan] "
                    f"[underline]{escape_markup(definition.source_url)}[/underline]"
                )
                try:
                    webbrowser.open(definition.source_url)
                except Exception:
                    pass
            else:
                msg = (
                    "Source confirmation required before automated install can be enabled."
                    if definition.source_status == SourceStatus.MANUAL_REQUIRED
                    else "Source link unavailable for this tool."
                )
                self.query_one("#tools-status", Static).update(
                    f"[bright_yellow]{escape_markup(msg)}[/bright_yellow]"
                )
            return
        if not bid.startswith("tool-install-"):
            return
        key = bid.removeprefix("tool-install-")
        meta = _installer_for(key)
        if meta is None:
            return
        reason = _tool_unavailable_reason(key)
        if reason:
            self.query_one("#tools-status", Static).update(
                f"[bright_yellow]{escape_markup(reason)}[/bright_yellow]"
            )
            self.notify(reason, title="Tools", severity="warning", timeout=10)
            return
        label, installer = meta
        btn = event.button
        self._start_spinner(btn)
        self.query_one("#tools-status", Static).update(
            f"[yellow]⏳ Installing {label}…[/yellow]"
        )
        self.run_worker(
            lambda: self._do_install(key, label, installer, btn),
            thread=True,
            exclusive=False,
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
        backup_msg = ""
        try:
            definition = get_tool_definition(key)
            if definition and definition.backup_policy:
                backup_ok, backup_msg = backup_before_install(definition.backup_policy)
                if not backup_ok:
                    ok, msg = False, backup_msg
                else:
                    ok, msg = installer()
                    msg = f"{backup_msg}\n{msg}" if msg else backup_msg
            else:
                ok, msg = installer()
        except Exception as e:
            ok, msg = False, f"error: {e}"

        def _done() -> None:
            self._stop_spinner(button.id)
            mark = "[green bold]✓[/green bold]" if ok else "[red bold]✗[/red bold]"
            lines = msg.splitlines() if msg else []
            snippet = (
                escape_markup(redact_secret_text("\n".join(lines[-8:])))
                if lines
                else ""
            )
            body = f"\n[dim]{snippet}[/dim]" if snippet else ""
            self.query_one("#tools-status", Static).update(
                f"{mark} {label} {'installed' if ok else 'failed'}{body}"
            )
            button.disabled = False
            button.label = "Install"
            last_line = redact_secret_text(lines[-1].strip()) if lines else ""
            if ok:
                # Flag the home "Local setup" panel to re-scan on resume.
                self.app.env_needs_refresh = True
                self.notify(
                    f"{label} updated",
                    title="Tools",
                    severity="information",
                    timeout=8,
                )
                # Re-probe just this row so the rest of the view stays put.
                self._refresh_one(key)
            else:
                summary = last_line or "see status panel for details"
                self.notify(
                    summary,
                    title=f"{label} failed",
                    severity="error",
                    timeout=15,
                )
                # Tag the row itself so the user can see which tool failed even
                # after the toast dismisses. State will only clear on Ctrl+R.
                try:
                    state_w = self.query_one(f"#tool-state-{key}", Static)
                    detail = self._installed_details.get(key, "")
                    suffix = f" [dim]{escape_markup(redact_secret_text(detail))}[/dim]" if detail else ""
                    state_w.update(
                        f"[bright_yellow]⬇ update available[/bright_yellow]{suffix} "
                        f"[bold red]· last attempt failed[/bold red]"
                    )
                except Exception:
                    pass

        self.app.call_from_thread(_done)
