"""Live console dashboard for the orchestrator (T023).

Per research.md R7 and data-model.md state machine: a separate Textual process
tails the SQLite event log on a 500 ms ``set_interval``, rendering a
``DataTable`` of recent runs and a ``Log`` of streamed event payloads. The
dashboard is read-only — it opens the database in SQLite read-only URI mode so
it can never accidentally take a write lock or mutate the log.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Log, Static

from orchestrator import eventlog
from orchestrator.config import Config

BANNER_LINES: tuple[str, ...] = (
    r"     /\     ",
    r"    /||\    ",
    r"   //||\\   ",
    r"  ╞══╪╪══╡  ",
)

BANNER_GRADIENT: tuple[str, ...] = (
    "bright_magenta",
    "magenta",
    "cyan",
    "bright_cyan",
)

_STATUS_GLYPHS: dict[str, str] = {
    "running": "[yellow]⟳[/yellow]",
    "completed": "[green]✓[/green]",
    "failed": "[red]✗[/red]",
    "skipped": "[yellow]⚠[/yellow]",
    "orphaned": "[magenta]○[/magenta]",
    "pending": "[dim]·[/dim]",
}

_MAX_LOG_LINES = 200
_MAX_TABLE_ROWS = 50
_REPO_COL_WIDTH = 20


def _render_banner(repo: str) -> Text:
    """Mirror ``setup/apply.py:render_banner`` gradient pattern with our own glyphs."""
    txt = Text()
    n = len(BANNER_LINES)
    for i, line in enumerate(BANNER_LINES):
        idx = (i * len(BANNER_GRADIENT)) // max(1, n - 1) if n > 1 else 0
        idx = min(idx, len(BANNER_GRADIENT) - 1)
        txt.append(line + "\n", style=f"bold {BANNER_GRADIENT[idx]}")
    txt.append(f"\n  ORCHESTRATOR · {repo}", style="bold bright_cyan")
    return txt


def _connect_readonly(path: Path) -> sqlite3.Connection:
    """Open the event log in SQLite read-only URI mode.

    Mirrors ``eventlog.connect`` (PARSE_DECLTYPES + Row factory) but appends
    ``?mode=ro`` so the dashboard cannot acquire a write lock or mutate the
    file even if a caller passed in a malicious connection.
    """
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def _humanize_relative(then_iso: str | None, *, now: datetime | None = None) -> str:
    if not then_iso:
        return "—"
    try:
        then = datetime.fromisoformat(then_iso)
    except ValueError:
        return "—"
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    delta_seconds = int((current - then).total_seconds())
    if delta_seconds < 0:
        delta_seconds = 0
    if delta_seconds < 60:
        return f"{delta_seconds}s ago"
    if delta_seconds < 3600:
        return f"{delta_seconds // 60}m ago"
    if delta_seconds < 86400:
        return f"{delta_seconds // 3600}h ago"
    return f"{delta_seconds // 86400}d ago"


def _humanize_duration(started_iso: str | None, ended_iso: str | None) -> str:
    if not started_iso or not ended_iso:
        return "—"
    try:
        started = datetime.fromisoformat(started_iso)
        ended = datetime.fromisoformat(ended_iso)
    except ValueError:
        return "—"
    seconds = int((ended - started).total_seconds())
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 1:
        return value[:limit]
    return value[: limit - 1] + "…"


def _format_event_line(event: eventlog.Event) -> str:
    """One-line summary for the Log widget."""
    payload_summary: str
    try:
        payload = json.loads(event.payload_json)
    except (TypeError, ValueError):
        payload_summary = event.payload_json
    else:
        if isinstance(payload, dict) and payload:
            parts = [f"{k}={payload[k]!r}" for k in list(payload)[:4]]
            payload_summary = ", ".join(parts)
        else:
            payload_summary = ""
    payload_summary = _truncate(payload_summary, 160)
    short_run = event.run_id[:8] if event.run_id else "--------"
    return (
        f"[{event.ts}] {event.kind} run={short_run} {event.level}"
        + (f" | {payload_summary}" if payload_summary else "")
    )


class OrchestratorDash(App[None]):
    """Read-only Textual dashboard tailing the orchestrator event log."""

    CSS = """
    Screen { background: $background; }

    #banner {
        height: auto;
        padding: 1 2;
        content-align: center middle;
    }

    #runs-table {
        height: 12;
        margin: 0 2;
        border: round $primary;
    }

    #event-log {
        height: 1fr;
        margin: 0 2 1 2;
        border: round $accent;
    }

    #status-footer {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    """

    BINDINGS = (
        Binding("q", "quit", "Quit", show=True),
        Binding("Q", "quit", "Quit", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False),
    )

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config: Config = config
        self._db_path: Path = config.orchestrator_db_path
        self._last_event_id: int = 0
        self._connected: bool = False
        self._poll_count: int = 0
        self._event_count: int = 0
        self._conn: sqlite3.Connection | None = None
        self._last_error: str | None = None

    def compose(self) -> ComposeResult:
        yield Static(_render_banner(self.config.orchestrator_repo), id="banner")
        yield DataTable(id="runs-table")
        yield Log(id="event-log", auto_scroll=True, max_lines=_MAX_LOG_LINES)
        yield Static("waiting for daemon · 0 events", id="status-footer")

    def on_mount(self) -> None:
        table = self.query_one("#runs-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_column("S", width=3)
        table.add_column("PR", width=8)
        table.add_column("Repo", width=_REPO_COL_WIDTH)
        table.add_column("SHA", width=9)
        table.add_column("Started", width=10)
        table.add_column("Duration", width=10)
        table.add_column("URL", width=40)

        self._open_connection_if_ready()
        self.set_interval(0.5, self._refresh)
        self._refresh()

    def _open_connection_if_ready(self) -> None:
        if self._conn is not None:
            return
        if not self._db_path.exists():
            return
        try:
            self._conn = _connect_readonly(self._db_path)
            self._connected = True
            self._last_error = None
        except sqlite3.DatabaseError as exc:
            self._conn = None
            self._connected = False
            self._last_error = str(exc)

    def _refresh(self) -> None:
        self._poll_count += 1

        if not self._db_path.exists():
            self._set_status("waiting for daemon · 0 events")
            return

        self._open_connection_if_ready()
        if self._conn is None:
            self._set_status(
                f"error: {self._last_error or 'unable to open db'} · retrying…"
            )
            return

        try:
            new_events = eventlog.tail_since(self._conn, self._last_event_id)
            runs = eventlog.runs_summary(self._conn)
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as exc:
            self._last_error = str(exc)
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None
            self._connected = False
            self._set_status(f"error: {exc} · retrying…")
            return

        if new_events:
            log = self.query_one("#event-log", Log)
            for event in new_events:
                log.write_line(_format_event_line(event))
                self._last_event_id = max(self._last_event_id, event.id)
            self._event_count += len(new_events)

        self._populate_runs(runs)
        self._set_status(
            f"connected · {self._event_count} events · last refresh: now"
        )

    def _populate_runs(self, runs: list[eventlog.Run]) -> None:
        table = self.query_one("#runs-table", DataTable)
        sorted_runs = sorted(
            runs,
            key=lambda r: r.started_at or "",
            reverse=True,
        )[:_MAX_TABLE_ROWS]

        table.clear()
        for run in sorted_runs:
            table.add_row(*self._row_for(run))

    @staticmethod
    def _row_for(run: eventlog.Run) -> tuple[str, str, str, str, str, str, str]:
        glyph = _STATUS_GLYPHS.get(run.state, run.state)
        pr = f"#{run.pr_number}" if run.pr_number else "—"
        repo = _truncate(run.repo, _REPO_COL_WIDTH) if run.repo else "—"
        sha = run.head_sha[:7] if run.head_sha else "—"
        started = _humanize_relative(run.started_at)
        terminal = run.ended_at is not None
        duration = _humanize_duration(run.started_at, run.ended_at) if terminal else "—"
        if run.artifact_url:
            url_cell = f"[link={run.artifact_url}]{run.artifact_url}[/link]"
        else:
            url_cell = "—"
        return (glyph, pr, repo, sha, started, duration, url_cell)

    def _set_status(self, message: str) -> None:
        self.query_one("#status-footer", Static).update(message)


__all__ = ["OrchestratorDash"]
