# -*- coding: utf-8 -*-
"""ClaudeStatsPanel — home-screen widget. Account type + plan usage from `claude /status`.

Never prints token / API-key values; falls back to ~/.claude.json when claude is missing.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Static

from cabal.claude_cli import _run_claude_cli


@dataclass
class ClaudeAccountStatus:
    account_type: str = "unknown"
    email: str | None = None
    signed_in: bool = False
    five_hour_used_pct: int | None = None
    weekly_cap_used_pct: int | None = None
    active_model: str | None = None
    token_present: bool = False
    raw_status_output: str | None = None
    error: str | None = None


_RE_EMAIL = re.compile(r"^\s*Account:\s+(\S+@\S+?)(?:\s|\()", re.MULTILINE)
_RE_PLAN  = re.compile(r"\((Pro|Max 20x|Max 5x|Team|Enterprise|API)\)")
_RE_MODEL = re.compile(r"^\s*Active model:\s+(\S+)", re.MULTILINE)
_RE_5HR   = re.compile(r"^\s*5-hour message usage:\s+(\d+)\s*%", re.MULTILINE)
_RE_WEEK  = re.compile(r"^\s*Weekly cap:\s+(\d+)\s*%", re.MULTILINE)


def parse_status(stdout: str) -> ClaudeAccountStatus:
    st = ClaudeAccountStatus()
    m = _RE_EMAIL.search(stdout)
    if m:
        st.email = m.group(1).strip()
    m = _RE_PLAN.search(stdout)
    if m:
        st.account_type = m.group(1)
    m = _RE_MODEL.search(stdout)
    if m:
        st.active_model = m.group(1)
    m = _RE_5HR.search(stdout)
    if m:
        st.five_hour_used_pct = int(m.group(1))
    m = _RE_WEEK.search(stdout)
    if m:
        st.weekly_cap_used_pct = int(m.group(1))
    st.signed_in = bool(st.email) or "signed in" in stdout.lower()
    if not (st.email or st.account_type != "unknown" or st.active_model
            or st.five_hour_used_pct is not None or st.weekly_cap_used_pct is not None):
        st.raw_status_output = stdout
    return st


def read_claude_dot_json_fallback() -> ClaudeAccountStatus:
    st = ClaudeAccountStatus(error="claude CLI not installed")
    p = Path.home() / ".claude.json"
    if not p.exists():
        return st
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return st
    oauth = (data or {}).get("oauthAccount") or {}
    if oauth.get("emailAddress"):
        st.email = oauth["emailAddress"]
        st.signed_in = True
    if oauth.get("organizationUuid"):
        st.token_present = True
    return st


class ClaudeStatsPanel(Widget):
    """Account type, plan usage, active model — read from `claude /status` with a `~/.claude.json` fallback."""

    DEFAULT_CSS = """
    ClaudeStatsPanel {
        height: auto;
        padding: 1 2;
        margin: 0 2;
        background: $boost;
        border: round $primary;
    }
    ClaudeStatsPanel #cs-title { content-align: left middle; height: 1; }
    ClaudeStatsPanel #cs-body { height: auto; padding: 0 0 0 0; }
    ClaudeStatsPanel #cs-actions { height: 3; padding: 0; margin: 1 0 0 0; }
    ClaudeStatsPanel #cs-actions Button { min-width: 16; height: 3; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._status: ClaudeAccountStatus | None = None

    def compose(self) -> ComposeResult:
        yield Static("[bold bright_magenta]✦ Claude account[/bold bright_magenta]", id="cs-title")
        yield Static("[dim]Loading…[/dim]", id="cs-body")
        with Horizontal(id="cs-actions"):
            yield Button("Refresh (Ctrl+S)", id="cs-refresh", variant="default")

    def on_mount(self) -> None:
        self.refresh_stats()

    def refresh_stats(self) -> None:
        self.query_one("#cs-body", Static).update("[dim italic]Loading…[/dim italic]")
        self.run_worker(self._refresh_worker, thread=True, exclusive=True)

    def _refresh_worker(self) -> None:
        if shutil.which("claude"):
            rc, out, err = _run_claude_cli(["-p", "/status"], timeout=15)
            if rc == 0 and out:
                st = parse_status(out)
                self._enrich_with_token_presence(st)
                self.app.call_from_thread(self._set_status, st)
                return
            st = read_claude_dot_json_fallback()
            if not st.error:
                st.error = (err or out or "").strip()[:200] or f"claude /status exited {rc}"
            self.app.call_from_thread(self._set_status, st)
            return
        st = read_claude_dot_json_fallback()
        self.app.call_from_thread(self._set_status, st)

    def _enrich_with_token_presence(self, st: ClaudeAccountStatus) -> None:
        p = Path.home() / ".claude.json"
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return
        oauth = (data or {}).get("oauthAccount") or {}
        if oauth.get("organizationUuid"):
            st.token_present = True

    def _set_status(self, st: ClaudeAccountStatus) -> None:
        self._status = st
        self.query_one("#cs-body", Static).update(self._render(st))

    def _render(self, st: ClaudeAccountStatus) -> Text:
        lines: list[str] = []
        if st.error:
            lines.append(f"[yellow]{st.error}[/yellow]")
        if st.email:
            lines.append(f"[bold]Signed in:[/bold] {st.email}")
        else:
            lines.append("[dim]not signed in — run `claude /login`[/dim]")
        lines.append(f"[bold]Account:[/bold] {st.account_type}")
        if st.active_model:
            lines.append(f"[bold]Active model:[/bold] {st.active_model}")
        if st.five_hour_used_pct is not None:
            colour = "green" if st.five_hour_used_pct < 70 else "yellow" if st.five_hour_used_pct < 95 else "red"
            lines.append(f"[bold]5-hour usage:[/bold] [{colour}]{st.five_hour_used_pct}%[/{colour}]")
        if st.weekly_cap_used_pct is not None:
            colour = "green" if st.weekly_cap_used_pct < 70 else "yellow" if st.weekly_cap_used_pct < 95 else "red"
            lines.append(f"[bold]Weekly cap:[/bold] [{colour}]{st.weekly_cap_used_pct}%[/{colour}]")
        token_disp = "[green]✓ token present[/green]" if st.token_present else "[dim]✗ no token[/dim]"
        lines.append(f"[bold]Auth:[/bold] {token_disp}")
        if st.raw_status_output:
            lines.append("[dim]could not parse — raw /status below:[/dim]")
            lines.append(f"[dim]{st.raw_status_output.strip()}[/dim]")
        return Text.from_markup("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if (event.button.id or "") == "cs-refresh":
            self.refresh_stats()
