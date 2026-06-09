# -*- coding: utf-8 -*-
"""UpdatePanel — async checker; shows behind/ahead status and a Pull button."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Static

from cabal import widget_cache
from cabal.updates import check_for_updates, do_git_pull

_CACHE_KEY = "updates"


class UpdatePanel(Widget):
    """Async update checker — compares local HEAD to origin and offers git pull."""

    DEFAULT_CSS = """
    UpdatePanel {
        height: auto;
        margin: 0 2 0 0;
    }
    #update-row {
        height: auto;
        align-vertical: middle;
        /* margin/padding are pinned to 0 in app.py too: the app's global
           `Horizontal` rule outranks this DEFAULT_CSS by source, so the
           left-alignment override has to live at app level to win. */
        padding: 0;
        margin: 0;
    }
    #update-msg {
        width: 1fr;
        padding: 0 1 0 0;
        content-align: left middle;
        height: auto;
    }
    #btn-pull { margin: 0; }
    #update-branch {
        height: 1;
        padding: 0 1;
        margin: 0 0 0 0;
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="update-row"):
            yield Static("[dim]Checking for updates…[/dim]", id="update-msg")
            yield Button("⬇ Pull update", id="btn-pull", variant="warning")
        yield Static("", id="update-branch")

    def on_mount(self) -> None:
        self.query_one("#btn-pull").display = False
        self.query_one("#update-branch").display = False
        cached = widget_cache.load_entry(_CACHE_KEY)
        if isinstance(cached, dict):
            self._apply(cached, from_cache=True)
        self.run_worker(self._check, thread=True, exclusive=True)

    def _check(self) -> None:
        result = check_for_updates()
        widget_cache.save_entry(_CACHE_KEY, result)
        self.app.call_from_thread(self._apply, result)

    def _apply(self, result: dict, from_cache: bool = False) -> None:
        msg = self.query_one("#update-msg", Static)
        btn = self.query_one("#btn-pull", Button)
        status = result["status"]
        # Never paint a stale "behind"/branch from cache — the cached entry may
        # reflect a different branch the checkout has since left. Show a neutral
        # placeholder and let the live check confirm.
        if from_cache and status != "up_to_date":
            msg.update("[dim]Checking for updates…[/dim]")
            return
        btn.display = False
        self.query_one("#update-branch").display = False
        if status == "up_to_date":
            date = result.get("date", "")
            date_suffix = f"  [dim]{date}[/dim]" if date else ""
            msg.update(
                f"[green bold]✓ Latest version[/green bold]  "
                f"[dim]{result['hash']}[/dim]{date_suffix}"
            )
        elif status == "behind":
            count = result.get("behind_count")
            subject = result.get("subject", "")
            count_str = f" ({count})" if count else ""
            subject_line = f"\n[dim]· {subject}[/dim]" if subject else ""
            msg.update(
                f"[yellow bold]⬆ Update available{count_str}[/yellow bold]  "
                f"[dim]{result['local']} → {result['remote']}[/dim]"
                f"{subject_line}"
            )
            btn.display = True
            branch = result.get("branch")
            if branch:
                branch_row = self.query_one("#update-branch", Static)
                branch_row.update(
                    f"[dim]↳ pulls into active branch: [/dim][bold]{branch}[/bold]"
                )
                branch_row.display = True
        elif status == "no_upstream":
            msg.update("[dim]branch has no upstream — updates not tracked[/dim]")
        elif status == "no_git":
            msg.update("[dim]git not found — cannot check for updates[/dim]")
        else:
            msg.update("[dim]⚠ Could not reach remote[/dim]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-pull":
            event.stop()
            self.query_one("#btn-pull").display = False
            self.query_one("#update-branch").display = False
            self.query_one("#update-msg", Static).update("[yellow]Pulling…[/yellow]")
            self.run_worker(self._pull, thread=True, exclusive=True)

    def _pull(self) -> None:
        ok, output = do_git_pull()

        def _done() -> None:
            msg = self.query_one("#update-msg", Static)
            if ok:
                msg.update(
                    "[green]✓ Pulled — restart the wizard to apply changes[/green]"
                )
            else:
                msg.update(f"[red]✗ Pull failed:[/red] [dim]{output[:120]}[/dim]")
                self.query_one("#btn-pull").display = True

        self.app.call_from_thread(_done)
