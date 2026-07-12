# -*- coding: utf-8 -*-
"""ContextGuardScreen — toggle + tune the opt-in /compact nudge in ~/.claude/context-guard-policy.json."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Input, Static

from cabal.app_widgets import AppHeader
from cabal.context_guard_policy import (
    BUILTIN_DEFAULTS,
    load_policy,
    policy_source,
    save_policy,
)


class ContextGuardScreen(Screen):
    """Edit the opt-in context-usage nudge policy: enabled, threshold %, assumed max tokens."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    CSS = """
    ContextGuardScreen { align: center middle; }
    ContextGuardScreen VerticalScroll { width: 80; height: auto; max-height: 90%; }
    .cg-card {
        width: 76;
        height: auto;
        padding: 1 2;
        margin: 1 0 0 0;
        background: $boost;
        border: round #CC006B;
    }
    .cg-card Label { margin: 1 0 0 0; color: #5FAFFF; text-style: bold; }
    .cg-card Input { margin: 0 0 0 0; }
    .cg-actions { height: 3; margin-top: 1; align-horizontal: center; }
    .cg-actions Button { margin: 0 1; }
    .cg-status { height: auto; margin: 1 0 0 0; }
    .cg-hint { color: $text-muted; margin: 0 0 0 0; }
    """

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            with Vertical(classes="cg-card", id="cg-card"):
                yield Static(
                    "[bold bright_magenta]✦ Context Guard ✦[/bold bright_magenta]\n"
                    "[dim]Opt-in advisory nudge: when estimated context usage crosses your "
                    "threshold, a UserPromptSubmit hook and a statusline chip both suggest "
                    "running /compact. This can never force or trigger compaction — no "
                    "Claude Code hook can do that — it only asks. Disabled by default. "
                    "Saved to ~/.claude/context-guard-policy.json.[/dim]"
                )
                yield Checkbox("Enabled", id="cg-enabled", value=False)
                yield Static("threshold_percent (1-100)", classes="cg-hint")
                yield Input(
                    id="cg-threshold",
                    placeholder=str(BUILTIN_DEFAULTS["threshold_percent"]),
                )
                yield Static(
                    "max_context_tokens (your assumed model context window)",
                    classes="cg-hint",
                )
                yield Input(
                    id="cg-max-tokens",
                    placeholder=str(BUILTIN_DEFAULTS["max_context_tokens"]),
                )
                yield Static("", id="cg-source", classes="cg-hint")
                with Horizontal(classes="cg-actions"):
                    yield Button("Save", id="cg-save", variant="primary")
                    yield Button("Reload", id="cg-reload", variant="default")
                    yield Button("Back", id="cg-back", variant="default")
                yield Static("", id="cg-status", classes="cg-status")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        pol = load_policy()
        self.query_one("#cg-enabled", Checkbox).value = bool(pol.get("enabled", False))
        self.query_one("#cg-threshold", Input).value = str(
            pol.get("threshold_percent", BUILTIN_DEFAULTS["threshold_percent"])
        )
        self.query_one("#cg-max-tokens", Input).value = str(
            pol.get("max_context_tokens", BUILTIN_DEFAULTS["max_context_tokens"])
        )
        self.query_one("#cg-source", Static).update(f"[dim]Source: {policy_source()}[/dim]")
        self.query_one("#cg-status", Static).update("[dim]Loaded current policy.[/dim]")

    @staticmethod
    def _parse_positive_int(raw: str, fallback: int) -> tuple[int | None, str | None]:
        raw = raw.strip()
        if not raw:
            return fallback, None
        try:
            value = int(raw)
        except ValueError:
            return None, f"'{raw}' is not a whole number"
        if value <= 0:
            return None, "must be greater than 0"
        return value, None

    def _save(self) -> None:
        threshold, threshold_err = self._parse_positive_int(
            self.query_one("#cg-threshold", Input).value,
            BUILTIN_DEFAULTS["threshold_percent"],
        )
        if threshold is not None and threshold > 100:
            threshold, threshold_err = None, "must be 100 or less"
        max_tokens, max_tokens_err = self._parse_positive_int(
            self.query_one("#cg-max-tokens", Input).value,
            BUILTIN_DEFAULTS["max_context_tokens"],
        )

        errors = [
            f"threshold_percent {msg}"
            for msg in (threshold_err,)
            if msg
        ] + [f"max_context_tokens {msg}" for msg in (max_tokens_err,) if msg]
        if errors:
            self.query_one("#cg-status", Static).update(
                "[red]✗ " + "; ".join(errors) + "[/red]"
            )
            return

        policy = {
            "enabled": self.query_one("#cg-enabled", Checkbox).value,
            "threshold_percent": threshold,
            "max_context_tokens": max_tokens,
        }
        try:
            written = save_policy(policy)
        except OSError as e:
            self.query_one("#cg-status", Static).update(f"[red]✗ Write failed: {e}[/red]")
            return
        self.query_one("#cg-source", Static).update(f"[dim]Source: {written}[/dim]")
        self.query_one("#cg-status", Static).update(f"[green]✓ Saved → {written}[/green]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "cg-back":
            self.app.pop_screen()
        elif bid == "cg-save":
            self._save()
        elif bid == "cg-reload":
            self._load()
