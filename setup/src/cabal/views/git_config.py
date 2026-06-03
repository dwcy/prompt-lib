# -*- coding: utf-8 -*-
"""GitConfigScreen — global/local user identity + agent commit policy editor."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
)

from cabal.app_widgets import AppHeader
from cabal.git_policy import BUILTIN_DEFAULTS, load_policy, policy_source, save_policy

Scope = Literal["global", "local"]


class GitConfigScreen(Screen):
    """Edit global/local git user identity and the agent commit policy in ~/.claude/git-policy.json."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    CSS = """
    GitConfigScreen { align: center middle; }
    GitConfigScreen VerticalScroll { width: 80; height: auto; max-height: 90%; }
    .git-card {
        width: 76;
        height: auto;
        padding: 1 2;
        margin: 1 0 0 0;
        background: $boost;
        border: round $primary;
    }
    .git-card Label { margin: 1 0 0 0; color: #5FAFFF; text-style: bold; }
    .git-card Input { margin: 0 0 0 0; }
    .git-card RadioSet { margin: 0 0 1 0; }
    .git-actions { height: 3; margin-top: 1; align-horizontal: center; }
    .git-actions Button { margin: 0 1; }
    .git-status { height: auto; margin: 1 0 0 0; }
    .git-hint { color: $text-muted; margin: 0 0 0 0; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._scope: Scope = "global"
        self._repo_root: Path | None = self._detect_repo(Path.cwd())

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            with Vertical(classes="git-card", id="git-user-card"):
                yield Static(
                    "[bold bright_magenta]✦ Git user identity ✦[/bold bright_magenta]\n"
                    "[dim]user.name and user.email — global writes to ~/.gitconfig, "
                    "local writes to .git/config in the current repo.[/dim]"
                )
                with RadioSet(id="git-scope"):
                    yield RadioButton(
                        "Global (~/.gitconfig)", id="scope-global", value=True
                    )
                    yield RadioButton(
                        f"Local ({self._repo_root})"
                        if self._repo_root
                        else "Local (no git repo at cwd)",
                        id="scope-local",
                        value=False,
                    )
                yield Label("user.name")
                yield Input(id="git-name", placeholder="Your name")
                yield Label("user.email")
                yield Input(id="git-email", placeholder="you@example.com")
                with Horizontal(classes="git-actions"):
                    yield Button("Save", id="git-save", variant="primary")
                    yield Button("Reload", id="git-reload", variant="default")
                    yield Button("Back", id="git-back", variant="default")
                yield Static("", id="git-status", classes="git-status")

            with Vertical(classes="git-card", id="git-policy-card"):
                yield Static(
                    "[bold bright_magenta]✦ Agent commit policy ✦[/bold bright_magenta]\n"
                    "[dim]Identity Claude uses for commits, plus type / branch / tag guardrails. "
                    "Saved to ~/.claude/git-policy.json.[/dim]"
                )
                yield Label("agent_name")
                yield Input(
                    id="pol-agent-name", placeholder=BUILTIN_DEFAULTS["agent_name"]
                )
                yield Label("agent_email")
                yield Input(
                    id="pol-agent-email", placeholder=BUILTIN_DEFAULTS["agent_email"]
                )
                yield Label("allowed_types (comma-separated)")
                yield Input(
                    id="pol-allowed-types",
                    placeholder="feat, task, fix, refactor, test, docs",
                )
                yield Label("refuse_on_branches (comma-separated)")
                yield Input(id="pol-refuse-branches", placeholder="main, master")
                yield Checkbox("tags.agent_may_tag", id="pol-may-tag", value=False)
                yield Checkbox("tags.auto_push", id="pol-auto-push", value=False)
                yield Static("", id="pol-source", classes="git-hint")
                with Horizontal(classes="git-actions"):
                    yield Button("Save policy", id="pol-save", variant="primary")
                    yield Button("Reload policy", id="pol-reload", variant="default")
                yield Static("", id="pol-status", classes="git-status")
        yield Footer()

    def on_mount(self) -> None:
        if not self._repo_root:
            self.query_one("#scope-local", RadioButton).disabled = True
        self._load_user()
        self._load_policy()

    @staticmethod
    def _detect_repo(start: Path) -> Path | None:
        for p in (start, *start.parents):
            if (p / ".git").exists():
                return p
        return None

    @staticmethod
    def _git() -> str | None:
        return shutil.which("git")

    def _read(self, key: str, scope: Scope) -> str | None:
        git = self._git()
        if not git:
            return None
        cmd = [git]
        if scope == "local" and self._repo_root:
            cmd += ["-C", str(self._repo_root)]
        cmd += ["config", f"--{scope}", key]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=3, check=False
            )
        except (OSError, subprocess.SubprocessError):
            return None
        v = (r.stdout or "").strip()
        return v or None

    def _write(self, key: str, value: str, scope: Scope) -> tuple[bool, str]:
        git = self._git()
        if not git:
            return False, "git not found"
        cmd = [git]
        if scope == "local" and self._repo_root:
            cmd += ["-C", str(self._repo_root)]
        cmd += ["config", f"--{scope}", key, value]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=3, check=False
            )
        except (OSError, subprocess.SubprocessError) as e:
            return False, str(e)
        return r.returncode == 0, (r.stderr or "").strip()

    def _load_user(self) -> None:
        if not self._git():
            self.query_one("#git-status", Static).update(
                "[red]✗ git not found on PATH — install git first[/red]"
            )
            return
        if self._scope == "local" and not self._repo_root:
            self.query_one("#git-name", Input).value = ""
            self.query_one("#git-email", Input).value = ""
            self.query_one("#git-status", Static).update(
                "[yellow]No git repo at current working directory — local scope unavailable.[/yellow]"
            )
            return
        self.query_one("#git-name", Input).value = (
            self._read("user.name", self._scope) or ""
        )
        self.query_one("#git-email", Input).value = (
            self._read("user.email", self._scope) or ""
        )
        where = (
            self._repo_root if self._scope == "local" else Path.home() / ".gitconfig"
        )
        self.query_one("#git-status", Static).update(
            f"[dim]Loaded {self._scope} values from {where}.[/dim]"
        )

    def _save_user(self) -> None:
        if self._scope == "local" and not self._repo_root:
            self.query_one("#git-status", Static).update(
                "[red]Cannot save local — no git repo at current working directory.[/red]"
            )
            return
        name = self.query_one("#git-name", Input).value.strip()
        email = self.query_one("#git-email", Input).value.strip()
        results: list[tuple[str, bool, str]] = []
        for key, value in (("user.name", name), ("user.email", email)):
            if value:
                ok, msg = self._write(key, value, self._scope)
                results.append((key, ok, msg))
        if not results:
            self.query_one("#git-status", Static).update(
                "[yellow]Nothing to save — both fields are empty.[/yellow]"
            )
            return
        lines = [
            f"{'[green]✓[/]' if ok else '[red]✗[/]'} --{self._scope} {key}"
            + (f" [dim]{msg}[/dim]" if msg else "")
            for key, ok, msg in results
        ]
        self.query_one("#git-status", Static).update("\n".join(lines))

    def _load_policy(self) -> None:
        pol = load_policy()
        self.query_one("#pol-agent-name", Input).value = str(pol.get("agent_name", ""))
        self.query_one("#pol-agent-email", Input).value = str(
            pol.get("agent_email", "")
        )
        self.query_one("#pol-allowed-types", Input).value = ", ".join(
            pol.get("allowed_types", [])
        )
        self.query_one("#pol-refuse-branches", Input).value = ", ".join(
            pol.get("refuse_on_branches", [])
        )
        tags = pol.get("tags", {}) or {}
        self.query_one("#pol-may-tag", Checkbox).value = bool(
            tags.get("agent_may_tag", False)
        )
        self.query_one("#pol-auto-push", Checkbox).value = bool(
            tags.get("auto_push", False)
        )
        self.query_one("#pol-source", Static).update(
            f"[dim]Source: {policy_source()}[/dim]"
        )
        self.query_one("#pol-status", Static).update(
            "[dim]Loaded current policy.[/dim]"
        )

    @staticmethod
    def _split_csv(s: str) -> list[str]:
        return [item.strip() for item in s.split(",") if item.strip()]

    def _save_policy(self) -> None:
        policy = {
            "agent_name": self.query_one("#pol-agent-name", Input).value.strip()
            or BUILTIN_DEFAULTS["agent_name"],
            "agent_email": self.query_one("#pol-agent-email", Input).value.strip()
            or BUILTIN_DEFAULTS["agent_email"],
            "allowed_types": self._split_csv(
                self.query_one("#pol-allowed-types", Input).value
            )
            or list(BUILTIN_DEFAULTS["allowed_types"]),
            "refuse_on_branches": self._split_csv(
                self.query_one("#pol-refuse-branches", Input).value
            )
            or list(BUILTIN_DEFAULTS["refuse_on_branches"]),
            "tags": {
                "agent_may_tag": self.query_one("#pol-may-tag", Checkbox).value,
                "auto_push": self.query_one("#pol-auto-push", Checkbox).value,
            },
        }
        try:
            written = save_policy(policy)
        except OSError as e:
            self.query_one("#pol-status", Static).update(
                f"[red]✗ Write failed: {e}[/red]"
            )
            return
        self.query_one("#pol-source", Static).update(f"[dim]Source: {written}[/dim]")
        self.query_one("#pol-status", Static).update(
            f"[green]✓ Saved → {written}[/green]"
        )

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id != "git-scope":
            return
        self._scope = "local" if event.pressed.id == "scope-local" else "global"
        self._load_user()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "git-back":
            self.app.pop_screen()
        elif bid == "git-save":
            self._save_user()
        elif bid == "git-reload":
            self._load_user()
        elif bid == "pol-save":
            self._save_policy()
        elif bid == "pol-reload":
            self._load_policy()
