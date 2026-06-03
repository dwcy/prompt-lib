# -*- coding: utf-8 -*-
"""ClaudeStatsPanel — home-screen widget. Email + token state from `~/.claude.json`.

Plan tier, 5-hour usage, weekly cap, and active model are only available from
the interactive `claude` UI's `/status` panel — `claude -p /status` sends the
literal text as a prompt and returns model output, not the slash-command panel.
So we don't shell out at all: a local JSON read is instant, free, and reliable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


@dataclass
class ClaudeAccountStatus:
    email: str | None = None
    signed_in: bool = False
    token_present: bool = False
    error: str | None = None


def read_claude_account_state() -> ClaudeAccountStatus:
    """Read `~/.claude.json` and surface the email + token presence.

    Returns an empty status (`signed_in=False`) if the file is missing or
    unreadable — never raises.
    """
    st = ClaudeAccountStatus()
    p = Path.home() / ".claude.json"
    if not p.exists():
        st.error = "~/.claude.json not found — run `claude /login`"
        return st
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        st.error = "~/.claude.json could not be parsed"
        return st
    oauth = (data or {}).get("oauthAccount") or {}
    if oauth.get("emailAddress"):
        st.email = oauth["emailAddress"]
        st.signed_in = True
    if oauth.get("organizationUuid"):
        st.token_present = True
    return st


class ClaudeStatsPanel(Widget):
    """Email + token state from `~/.claude.json`. Plan / usage / model not available headlessly."""

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
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._status: ClaudeAccountStatus | None = None

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold bright_magenta]✦ Claude account[/bold bright_magenta]", id="cs-title"
        )
        yield Static("[dim]Loading…[/dim]", id="cs-body")

    def on_mount(self) -> None:
        self.refresh_stats()

    def refresh_stats(self) -> None:
        st = read_claude_account_state()
        self._set_status(st)

    def _set_status(self, st: ClaudeAccountStatus) -> None:
        self._status = st
        self.query_one("#cs-body", Static).update(self._render_body(st))

    def _render_body(self, st: ClaudeAccountStatus) -> Text:
        lines: list[str] = []
        if st.email:
            lines.append(f"[bold]Signed in:[/bold] {st.email}")
        else:
            lines.append("[dim]not signed in — run `claude /login`[/dim]")
        token_disp = (
            "[green]✓ token present[/green]"
            if st.token_present
            else "[dim]✗ no token[/dim]"
        )
        lines.append(f"[bold]Auth:[/bold] {token_disp}")
        if st.error:
            lines.append(f"[yellow]{st.error}[/yellow]")
        lines.append(
            "[dim]Plan, usage and active model only visible from the interactive `claude` UI (`/status`).[/dim]"
        )
        return Text.from_markup("\n".join(lines))
