# -*- coding: utf-8 -*-
"""CloneRepoScreen — pick a destination and clone a GitHub repo with live output."""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, RichLog, Static


def default_projects_dir() -> Path:
    """Default base directory new clones land in."""
    if platform.system() == "Windows":
        return Path("C:/projects")
    return Path.home() / "projects"


class CloneRepoScreen(ModalScreen):
    """Two-phase modal: choose a destination, then stream `gh repo clone` output."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    CloneRepoScreen { align: center middle; background: $background 70%; }
    #clone-dialog {
        width: 86; height: 30; padding: 1 2;
        background: $panel; border: double $accent;
    }
    #clone-title { height: 2; content-align: left middle; }
    #clone-target {
        height: 3; padding: 0 1; margin: 1 0;
        background: $boost; border: round $primary; content-align: left middle;
    }
    #clone-choose-actions, #clone-run-actions {
        height: 3; margin-top: 1; align-horizontal: center;
    }
    #clone-choose-actions Button, #clone-run-actions Button { margin: 0 1; }
    #clone-cmd { height: auto; padding: 0 1; margin: 0 0 1 0; color: $text-muted; }
    #clone-log { height: 1fr; border: round $primary; background: $surface; }
    """

    def __init__(self, name_with_owner: str, repo_name: str) -> None:
        super().__init__()
        self.name_with_owner = name_with_owner
        self.repo_name = repo_name
        self._dest_base = default_projects_dir()
        self._proc: subprocess.Popen | None = None
        self._done = False
        self._success = False

    def compose(self) -> ComposeResult:
        with Container(id="clone-dialog"):
            yield Static(
                f"[bold bright_magenta]Clone[/bold bright_magenta] "
                f"[cyan]{self.name_with_owner}[/cyan]",
                id="clone-title",
            )
            with Vertical(id="clone-choose"):
                yield Static("", id="clone-target")
                with Horizontal(id="clone-choose-actions"):
                    yield Button("Browse  📁", id="clone-browse")
                    yield Button("Accept  ↵", id="clone-accept", variant="success")
                    yield Button("Cancel  Esc", id="clone-cancel", variant="error")
            with Vertical(id="clone-run"):
                yield Static("", id="clone-cmd")
                yield RichLog(id="clone-log", highlight=False, markup=True, wrap=True)
                with Horizontal(id="clone-run-actions"):
                    yield Button("Close", id="clone-close", variant="primary", disabled=True)

    def on_mount(self) -> None:
        self.query_one("#clone-run", Vertical).display = False
        self._refresh_target()
        self.query_one("#clone-accept", Button).focus()

    def _target(self) -> Path:
        return self._dest_base / self.repo_name

    def _refresh_target(self, note: str = "") -> None:
        msg = f"[dim]Clone into[/dim]  [bold]{self._target()}[/bold]"
        if note:
            msg += f"\n{note}"
        self.query_one("#clone-target", Static).update(msg)

    # ── choose phase ────────────────────────────────────────────────────────

    def _open_browser(self) -> None:
        from cabal.views.folder_browser import FolderBrowserScreen

        start = self._dest_base if self._dest_base.is_dir() else Path.home()

        def _cb(path: Path | None) -> None:
            if path is not None:
                self._dest_base = path
                self._refresh_target()

        self.app.push_screen(FolderBrowserScreen(start), _cb)

    def _accept(self) -> None:
        target = self._target()
        if target.exists() and any(target.iterdir()):
            self._refresh_target(
                f"[red]✗ {target.name}/ already exists and is not empty — "
                f"pick another location.[/red]"
            )
            return
        self._start_clone(target)

    # ── running phase ───────────────────────────────────────────────────────

    def _start_clone(self, target: Path) -> None:
        cmd_display = f"$ gh repo clone {self.name_with_owner} {target}"
        self.query_one("#clone-choose", Vertical).display = False
        self.query_one("#clone-run", Vertical).display = True
        self.query_one("#clone-cmd", Static).update(f"[dim]{cmd_display}[/dim]")
        self.run_worker(lambda t=target: self._clone_worker(t), thread=True, exclusive=True)

    def _clone_worker(self, target: Path) -> None:
        log = self.query_one("#clone-log", RichLog)
        gh = shutil.which("gh")
        if not gh:
            self.app.call_from_thread(self._on_done, 127, "gh CLI not found on PATH")
            return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.app.call_from_thread(self._on_done, 1, f"could not create {target.parent}: {e}")
            return

        cmd = [gh, "repo", "clone", self.name_with_owner, str(target)]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as e:
            self.app.call_from_thread(self._on_done, 1, str(e))
            return

        self._proc = proc
        try:
            assert proc.stdout is not None
            for line in iter(proc.stdout.readline, ""):
                s = line.rstrip()
                if s:
                    self.app.call_from_thread(log.write, s)
            rc = proc.wait()
        finally:
            self._proc = None
        self.app.call_from_thread(self._on_done, rc)

    def _on_done(self, rc: int, error: str = "") -> None:
        self._done = True
        self._success = rc == 0 and not error
        log = self.query_one("#clone-log", RichLog)
        if error:
            log.write(f"[red]✗ {error}[/red]")
        if self._success:
            log.write(f"[green]✓ Cloned into {self._target()}[/green]")
        else:
            log.write(f"[red]✗ Clone failed (exit {rc})[/red]")
        close = self.query_one("#clone-close", Button)
        close.disabled = False
        close.focus()

    def _result(self) -> Path | None:
        return self._target() if self._success else None

    def _terminate(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    # ── actions / events ────────────────────────────────────────────────────

    def action_cancel(self) -> None:
        in_run = self.query_one("#clone-run", Vertical).display
        if in_run and not self._done:
            self._terminate()  # abort; worker fires _on_done → Close enabled
            return
        self._terminate()
        self.dismiss(self._result())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "clone-browse":
            self._open_browser()
        elif bid == "clone-accept":
            self._accept()
        elif bid == "clone-cancel":
            self.dismiss(None)
        elif bid == "clone-close":
            self._terminate()
            self.dismiss(self._result())
