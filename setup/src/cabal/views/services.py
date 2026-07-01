# -*- coding: utf-8 -*-
"""ServicesScreen — view of the local agent services; lifecycle/install I/O via supervisor + installers.

The dashboard hand-off (App.suspend() + run service_supervisor.open_dashboard()'s
argv in the foreground) is the one allowed child-process here; the child owns the
terminal under suspend until it exits.
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
from cabal.widgets.service_log_panel import ServiceLogPanel
from cabal import service_supervisor

_ACTION_START = "start"
_ACTION_STOP = "stop"

# Service key -> installer callable used by the Setup action (FR-009).
_INSTALLERS: dict[str, callable] = {
    "a2a-bridge": a2a_bridge_install,
    "orchestrator": orchestrator_install,
}

_STATUS_GLYPHS: dict[ServiceStatus, tuple[str, str]] = {
    ServiceStatus.RUNNING: ("✓ running", "#FF5FD7"),
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
        height: auto;
        margin: 0 0 1 0;
    }
    ServicesScreen .svc-row-top {
        layout: horizontal;
        height: auto;
        align: left middle;
    }
    ServicesScreen .svc-name { width: 20; }
    ServicesScreen .svc-state { width: 18; content-align: left middle; }
    ServicesScreen .svc-body { width: 100%; margin: 0 0 0 1; }
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
        width: 8;
        min-width: 8;
        max-width: 8;
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
    ServicesScreen Button.svc-logs {
        background: #4B3B6B;
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
                "[dim]Local agent services; status refreshes on open, logs stream below.[/dim]",
                classes="panel",
            )
            with Vertical(classes="svc-group", id="svc-group"):
                yield Static("✦ Local Agent Services", classes="svc-group-title")
                for service in all_services():
                    yield from self._build_row(service)
            yield ServiceLogPanel(id="svc-log-panel")
        yield Footer(show_command_palette=False)

    def _build_row(self, service: ServiceDefinition):
        with Vertical(classes="svc-row", id=f"svc-row-{service.key}"):
            with Horizontal(classes="svc-row-top"):
                yield Static(
                    f"[white]{escape_markup(service.label)}[/]",
                    classes="svc-name",
                )
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
                    )
                    yield Button(
                        "Logs",
                        id=f"svc-logs-{service.key}",
                        classes="svc-action svc-logs",
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
            yield Static(self._body_markup(service), classes="svc-body")

    @staticmethod
    def _body_markup(service: ServiceDefinition) -> str:
        lines = [f"[dim]{escape_markup(service.description)}[/dim]"]
        if service.depends_on:
            deps = ", ".join(service.depends_on)
            lines.append(f"[dim italic]depends on {escape_markup(deps)}[/dim italic]")
        if not service.runnable:
            lines.append(
                "[dim italic]client-launched MCP server — no start/stop[/dim italic]"
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
        # Show exactly the action that applies to the current state: Setup when
        # not installed, Start when set up but not running (or blocked, to retry),
        # Stop only while running.
        can_start = status in (ServiceStatus.STOPPED, ServiceStatus.BLOCKED)
        visibility = (
            ("svc-setup", status == ServiceStatus.NOT_SET_UP),
            ("svc-start", can_start),
            ("svc-stop", status == ServiceStatus.RUNNING),
        )
        for prefix, visible in visibility:
            try:
                button = self.query_one(f"#{prefix}-{key}", Button)
            except Exception:
                continue
            button.display = visible

    @staticmethod
    def _build_status_label(status: ServiceStatus, detail: str) -> str:
        label, color = _STATUS_GLYPHS.get(status, ("? unknown", "white"))
        suffix = f" {escape_markup(detail)}" if detail else ""
        return f"[{color}]{label}{suffix}[/{color}]"

    def _show_error(self, message: str) -> None:
        self.notify(message, title="error", severity="error", timeout=12)

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
        if bid.startswith("svc-logs-"):
            self._open_logs(bid.removeprefix("svc-logs-"))
            return
        if not bid.startswith("svc-source-"):
            return
        key = bid.removeprefix("svc-source-")
        url = next(
            (s.source_url for s in all_services() if s.key == key and s.source_url), ""
        )
        if not url:
            return
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _dispatch_lifecycle(self, key: str, action: str) -> None:
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
        if action == _ACTION_START and state.status == ServiceStatus.RUNNING:
            self.app.call_from_thread(self._open_logs, key)
        self.app.call_from_thread(self._refresh_statuses)

    def _announce_lifecycle(self, key: str, state) -> None:
        if state.status == ServiceStatus.BLOCKED:
            message = state.detail or f"{key} could not start."
            self.notify(message, title=key, severity="warning", timeout=12)
        elif state.status == ServiceStatus.NOT_SET_UP:
            message = state.detail or f"{key} is not set up yet."
            self.notify(message, title=key, severity="warning", timeout=12)

    def _dispatch_setup(self, key: str) -> None:
        installer = _INSTALLERS.get(key)
        if installer is None:
            return
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
        self.notify(
            message,
            title=key,
            severity="information" if ok else "warning",
            timeout=12,
        )

    def _open_dashboard(self, key: str) -> None:
        argv, message = service_supervisor.open_dashboard(key)
        if argv is None:
            self.notify(message, title=key, severity="warning", timeout=12)
            return
        self._launch_foreground(argv)
        self._refresh_statuses()

    def _open_logs(self, key: str) -> None:
        label = next((s.label for s in all_services() if s.key == key), key)
        self.query_one(ServiceLogPanel).show(key, label)

    def _launch_foreground(self, argv: list[str]) -> None:
        """Hand the terminal to the dashboard child until it exits, then resume cabal."""
        with self.app.suspend():
            try:
                subprocess.run(argv)
            except OSError as exc:
                self.app.call_from_thread(self._show_error, str(exc))
