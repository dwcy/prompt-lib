# -*- coding: utf-8 -*-
"""ServiceLogScreen — live terminal-style tail of a service's captured output log."""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, RichLog, Static

from cabal import service_supervisor
from cabal.app_widgets import AppHeader

_REFRESH_SECONDS = 1.0
# Only ever seed the view with the log's tail so a huge run does not flood the widget.
_TAIL_BYTES = 64_000
_EMPTY_HINT = "No output yet — start the service to capture logs."


class ServiceLogScreen(Screen):
    """Stream a single service's captured stdout/stderr log, tailing new bytes on a timer."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "app.pop_screen", "Back"),
    ]

    CSS = """
    ServiceLogScreen .svc-log-box {
        height: 1fr;
        padding: 1 2;
        margin: 0 2 1 2;
        background: $boost;
        border: round #CC006B;
    }
    ServiceLogScreen .svc-log-title {
        text-style: bold;
        color: #5FAFFF;
        height: auto;
        margin: 0 0 1 0;
    }
    ServiceLogScreen RichLog {
        height: 1fr;
        background: $surface;
        border: round #355E3B;
        padding: 0 1;
    }
    """

    def __init__(self, key: str, label: str) -> None:
        super().__init__()
        self._key = key
        self._label = label
        self._path: Path = service_supervisor.log_path(key)
        self._offset = 0

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Vertical(classes="svc-log-box"):
            yield Static(
                f"[bold bright_magenta]✦ {escape_markup(self._label)} — logs ✦[/bold bright_magenta]\n"
                f"[dim]{escape_markup(str(self._path))}[/dim]",
                classes="svc-log-title",
            )
            yield RichLog(highlight=False, markup=False, wrap=False, id="svc-log-view")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._seed_tail()
        self.set_interval(_REFRESH_SECONDS, self._pull_new)

    def _seed_tail(self) -> None:
        view = self.query_one("#svc-log-view", RichLog)
        if not self._path.is_file():
            view.write(_EMPTY_HINT)
            self._offset = 0
            return
        try:
            size = self._path.stat().st_size
            start = max(0, size - _TAIL_BYTES)
            with self._path.open("r", encoding="utf-8", errors="replace") as fh:
                if start:
                    fh.seek(start)
                    fh.readline()  # drop the partial first line after a mid-line seek
                text = fh.read()
            self._offset = size
        except OSError as exc:
            view.write(f"Could not read log: {exc}")
            return
        if not text.strip():
            view.write(_EMPTY_HINT)
            return
        for line in text.splitlines():
            view.write(line)

    def _pull_new(self) -> None:
        if not self._path.is_file():
            return
        view = self.query_one("#svc-log-view", RichLog)
        try:
            size = self._path.stat().st_size
            if size < self._offset:
                # Log was truncated (a fresh start) — reseed from the top.
                view.clear()
                self._offset = 0
                self._seed_tail()
                return
            if size == self._offset:
                return
            with self._path.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(self._offset)
                text = fh.read()
            self._offset = size
        except OSError:
            return
        for line in text.splitlines():
            view.write(line)
