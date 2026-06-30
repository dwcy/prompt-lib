# -*- coding: utf-8 -*-
"""ServicesScreen — view of the local agent services; lifecycle/install I/O via supervisor + installers.

The dashboard hand-off (App.suspend() + run the resolved argv in the foreground)
is the one allowed child-process in this view; the argv is resolved by
service_supervisor.open_dashboard(), and the view only runs it under suspend so
the child owns the terminal until it exits.
"""

from __future__ import annotations

import subprocess
import webbrowser

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.installers.a2a_bridge import a2a_bridge_install
from cabal.installers.orchestrator import orchestrator_install
from cabal.service_catalog import ServiceDefinition, ServiceStatus, all_services
from cabal import service_supervisor

_ACTION_START = "start"
_ACTION_STOP = "stop"

# Service key -> installer callable used by the Setup action (FR-009).
_INSTALLERS: dict[str, callable] = {
    "a2a-bridge": a2a_bridge_install,
    "orchestrator": orchestrator_install,
}

_STATUS_GLYPHS: dict[ServiceStatus, tuple[str, str]] = {
    ServiceStatus.RUNNING: ("✓ running", "bright_green"),
    ServiceStatus.STOPPED: ("○ stopped", "bright_yellow"),
    ServiceStatus.NOT_SET_UP: ("✗ not set up", "red"),
    ServiceStatus.BLOCKED: ("✗ blocked", "red"),
    ServiceStatus.INFO_ONLY: ("ⓘ info-only", "cyan"),
}


class ServicesScreen(Screen):
    """List orchestrator, a2a-bridge, and mcp-bus with their command, source, and live status."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    CSS = """
    ServicesScreen .svc-group {
        height: auto;
        padding: 1 2;
        margin: 0 2 1 2;
        background: $boost;
        border: round #CC006B;
    }
    ServicesScreen .svc-group-title {
        text-style: bold;
        color: #5FAFFF;
        margin: 0 0 1 0;
    }
    ServicesScreen .svc-row {
        layout: horizontal;
        height: auto;
        align: left middle;
        margin: 0 0 1 0;
    }
    ServicesScreen .svc-name { width: 20; }
    ServicesScreen .svc-body { width: 1fr; }
    ServicesScreen .svc-state { width: 16; content-align: left middle; }
    ServicesScreen Button.svc-source,
    ServicesScreen Button.svc-source:hover,
    ServicesScreen Button.svc-source:focus {
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
    ServicesScreen Button.svc-action,
    ServicesScreen Button.svc-action:hover,
    ServicesScreen Button.svc-action:focus {
        width: 9;
        min-width: 9;
        max-width: 9;
        height: 1;
        min-height: 1;
        max-height: 1;
        padding: 0;
        margin: 0 1 0 0;
        border: none;
        color: white;
        text-style: bold;
        background: #1F6FEB;
        content-align: center middle;
    }
    ServicesScreen Button.svc-stop {
        background: #8B2635;
    }
    ServicesScreen Button.svc-setup {
        background: #355E3B;
    }
    ServicesScreen Button.svc-dash {
        width: 12;
        min-width: 12;
        max-width: 12;
        background: #6A3FB5;
    }
    """

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Local Agent Services ✦[/bold bright_magenta]\n"
                "[dim]The local agent services that power orchestration. Status "
                "refreshes on open.[/dim]",
                classes="panel",
            )
            with Vertical(classes="svc-group", id="svc-group"):
                yield Static("✦ Local Agent Services", classes="svc-group-title")
                for service in all_services():
                    yield from self._build_row(service)
            yield Static("", id="services-status", classes="panel")
        yield Footer(show_command_palette=False)

    def _build_row(self, service: ServiceDefinition):
        with Horizontal(classes="svc-row", id=f"svc-row-{service.key}"):
            yield Static(
                f"[white]{escape_markup(service.label)}[/]",
                classes="svc-name",
            )
            yield Static(self._body_markup(service), classes="svc-body")
            yield Static(
                "[dim]…[/dim]",
                classes="svc-state",
                id=f"svc-state-{service.key}",
            )
            if service.runnable:
                yield Button(
                    "Setup",
                    id=f"svc-setup-{service.key}",
                    classes="svc-action svc-setup",
                )
                yield Button(
                    "Start",
                    id=f"svc-start-{service.key}",
                    classes="svc-action svc-start",
                )
                yield Button(
                    "Stop",
                    id=f"svc-stop-{service.key}",
                    classes="svc-action svc-stop",
                    disabled=True,
                )
            if service.dashboard_command:
                yield Button(
                    "Dashboard",
                    id=f"svc-dash-{service.key}",
                    classes="svc-action svc-dash",
                )
            yield Button(
                "Read more",
                id=f"svc-source-{service.key}",
                classes="svc-source",
                disabled=not service.source_url,
            )

    @staticmethod
    def _body_markup(service: ServiceDefinition) -> str:
        lines = [
            f"[dim]{escape_markup(service.description)}[/dim]",
            f"[cyan]{escape_markup(service.run_command)}[/cyan]",
        ]
        if service.depends_on:
            deps = ", ".join(service.depends_on)
            lines.append(f"[dim italic]depends on {escape_markup(deps)}[/dim italic]")
        if not service.runnable:
            lines.append(
                "[dim italic]client-launched MCP server — no start/stop[/dim italic]"
            )
        if service.log_hint:
            lines.append(
                f"[dim italic]logs: {escape_markup(service.log_hint)}[/dim italic]"
            )
        return "\n".join(lines)

    def on_mount(self) -> None:
        self._refresh_statuses()

    def on_screen_resume(self) -> None:
        self._refresh_statuses()

    def action_refresh(self) -> None:
        self._refresh_statuses()

    def _refresh_statuses(self) -> None:
        self.run_worker(self._load_statuses, thread=True, exclusive=True)

    def _load_statuses(self) -> None:
        try:
            states = service_supervisor.statuses()
        except Exception as exc:
            self.app.call_from_thread(self._show_error, str(exc))
            return
        self.app.call_from_thread(self._apply_statuses, states)

    def _apply_statuses(self, states: dict) -> None:
        for key, state in states.items():
            try:
                widget = self.query_one(f"#svc-state-{key}", Static)
            except Exception:
                continue
            widget.update(self._build_status_label(state.status, state.detail))
            self._sync_controls(key, state.status)

    def _sync_controls(self, key: str, status: ServiceStatus) -> None:
        running = status == ServiceStatus.RUNNING
        not_set_up = status == ServiceStatus.NOT_SET_UP
        controls = (
            ("svc-setup", not not_set_up),
            ("svc-start", running or not_set_up),
            ("svc-stop", not running),
        )
        for prefix, disabled in controls:
            try:
                button = self.query_one(f"#{prefix}-{key}", Button)
            except Exception:
                continue
            button.disabled = disabled

    @staticmethod
    def _build_status_label(status: ServiceStatus, detail: str) -> str:
        label, color = _STATUS_GLYPHS.get(status, ("? unknown", "white"))
        suffix = f" [dim]{escape_markup(detail)}[/dim]" if detail else ""
        return f"[{color}]{label}[/{color}]{suffix}"

    def _show_error(self, message: str) -> None:
        self.query_one("#services-status", Static).update(
            f"[red]Status refresh failed: {escape_markup(message)}[/red]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("svc-start-"):
            self._dispatch_lifecycle(bid.removeprefix("svc-start-"), _ACTION_START)
            return
        if bid.startswith("svc-stop-"):
            self._dispatch_lifecycle(bid.removeprefix("svc-stop-"), _ACTION_STOP)
            return
        if bid.startswith("svc-setup-"):
            self._dispatch_setup(bid.removeprefix("svc-setup-"))
            return
        if bid.startswith("svc-dash-"):
            self._open_dashboard(bid.removeprefix("svc-dash-"))
            return
        if not bid.startswith("svc-source-"):
            return
        key = bid.removeprefix("svc-source-")
        url = next(
            (s.source_url for s in all_services() if s.key == key and s.source_url),
            "",
        )
        if not url:
            return
        self.query_one("#services-status", Static).update(
            f"[cyan]source:[/cyan] [underline]{escape_markup(url)}[/underline]"
        )
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _dispatch_lifecycle(self, key: str, action: str) -> None:
        verb = "Starting" if action == _ACTION_START else "Stopping"
        self.query_one("#services-status", Static).update(
            f"[cyan]{verb} {escape_markup(key)}…[/cyan]"
        )
        self.run_worker(
            lambda: self._run_lifecycle(key, action),
            thread=True,
            exclusive=False,
        )

    def _run_lifecycle(self, key: str, action: str) -> None:
        try:
            if action == _ACTION_START:
                state = service_supervisor.start(key)
            else:
                state = service_supervisor.stop(key)
        except Exception as exc:
            self.app.call_from_thread(self._show_error, str(exc))
            return
        self.app.call_from_thread(self._announce_lifecycle, key, state)
        self.app.call_from_thread(self._refresh_statuses)

    def _announce_lifecycle(self, key: str, state) -> None:
        if state.status == ServiceStatus.BLOCKED:
            message = state.detail or f"{key} could not start."
            self.query_one("#services-status", Static).update(
                f"[red]blocked:[/red] {escape_markup(message)}"
            )
            self.notify(message, title=key, severity="warning", timeout=12)
            return
        if state.status == ServiceStatus.NOT_SET_UP:
            message = state.detail or f"{key} is not set up yet."
            self.query_one("#services-status", Static).update(
                f"[yellow]{escape_markup(message)}[/yellow]"
            )
            return
        label, _color = _STATUS_GLYPHS.get(state.status, ("? unknown", "white"))
        self.query_one("#services-status", Static).update(
            f"[cyan]{escape_markup(key)}:[/cyan] {escape_markup(label)}"
        )

    def _dispatch_setup(self, key: str) -> None:
        installer = _INSTALLERS.get(key)
        if installer is None:
            return
        self.query_one("#services-status", Static).update(
            f"[cyan]Setting up {escape_markup(key)}…[/cyan]"
        )
        self.run_worker(
            lambda: self._run_setup(key, installer),
            thread=True,
            exclusive=False,
        )

    def _run_setup(self, key: str, installer) -> None:
        try:
            ok, message = installer()
        except Exception as exc:
            self.app.call_from_thread(self._show_error, str(exc))
            return
        self.app.call_from_thread(self._announce_setup, key, ok, message)
        self.app.call_from_thread(self._refresh_statuses)

    def _announce_setup(self, key: str, ok: bool, message: str) -> None:
        color = "green" if ok else "red"
        verb = "set up" if ok else "setup failed"
        self.query_one("#services-status", Static).update(
            f"[{color}]{escape_markup(key)} {verb}:[/{color}] {escape_markup(message)}"
        )
        self.notify(
            message,
            title=key,
            severity="information" if ok else "warning",
            timeout=12,
        )

    def _open_dashboard(self, key: str) -> None:
        argv, message = service_supervisor.open_dashboard(key)
        if argv is None:
            self.query_one("#services-status", Static).update(
                f"[yellow]{escape_markup(message)}[/yellow]"
            )
            self.notify(message, title=key, severity="warning", timeout=12)
            return
        self.query_one("#services-status", Static).update(
            f"[cyan]{escape_markup(message)}[/cyan]"
        )
        self._launch_foreground(argv)
        self._refresh_statuses()

    def _launch_foreground(self, argv: list[str]) -> None:
        """Hand the terminal to the dashboard child until it exits, then resume cabal."""
        with self.app.suspend():
            try:
                subprocess.run(argv)
            except OSError as exc:
                self.app.call_from_thread(self._show_error, str(exc))
