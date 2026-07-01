# -*- coding: utf-8 -*-
"""ServiceLogPanel — inline live-tail pane for a single service's captured output log."""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import RichLog, Static

from cabal import service_supervisor

_REFRESH_SECONDS = 1.0
# Only ever seed the view with the log's tail so a huge run does not flood the widget.
_TAIL_BYTES = 64_000
_EMPTY_HINT = (
    "No service selected — press Logs on a service, or start one, to stream its output."
)
_NO_OUTPUT_HINT = "No output yet — start the service to capture logs."


class ServiceLogPanel(Widget):
    """Embedded RichLog that tails the selected service's capture log, retargetable via show()."""

    DEFAULT_CSS = """
    ServiceLogPanel {
        height: 14;
        padding: 1 2;
        margin: 0 2 1 2;
        background: $boost;
        border: round #CC006B;
    }
    ServiceLogPanel #svc-log-title {
        text-style: bold;
        color: #5FAFFF;
        height: auto;
        margin: 0 0 1 0;
    }
    ServiceLogPanel RichLog {
        height: 1fr;
        background: $surface;
        border: round #355E3B;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._key: str | None = None
        self._path: Path | None = None
        self._offset = 0

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold bright_magenta]✦ Logs ✦[/bold bright_magenta]",
            id="svc-log-title",
        )
        yield RichLog(highlight=False, markup=False, wrap=False, id="svc-log-view")

    def on_mount(self) -> None:
        self.border_title = "Logs"
        self._seed_tail()
        self.set_interval(_REFRESH_SECONDS, self._pull_new)

    def show(self, key: str, label: str) -> None:
        """Retarget the panel to `key`: repaint the title, clear the log, reseed from its tail."""
        self._key = key
        self._path = service_supervisor.log_path(key)
        self.border_title = f"Logs: {label}"
        self.query_one("#svc-log-title", Static).update(
            f"[bold bright_magenta]✦ Logs: {escape_markup(label)} ✦[/bold bright_magenta]\n"
            f"[dim]{escape_markup(str(self._path))}[/dim]"
        )
        view = self.query_one("#svc-log-view", RichLog)
        view.clear()
        self._offset = 0
        self._seed_tail()

    def _seed_tail(self) -> None:
        view = self.query_one("#svc-log-view", RichLog)
        if self._key is None or self._path is None:
            view.write(_EMPTY_HINT)
            self._offset = 0
            return
        if not self._path.is_file():
            view.write(_NO_OUTPUT_HINT)
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
            view.write(_NO_OUTPUT_HINT)
            return
        for line in text.splitlines():
            view.write(line)

    def _pull_new(self) -> None:
        if self._key is None or self._path is None or not self._path.is_file():
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
