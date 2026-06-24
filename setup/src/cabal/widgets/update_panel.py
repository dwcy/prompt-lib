# -*- coding: utf-8 -*-
"""UpdatePanel — async checker; shows behind/ahead status and a Pull button."""

from __future__ import annotations

from typing import Callable

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Static

from cabal import widget_cache
from cabal.updates import check_for_updates, do_git_pull

_CACHE_KEY = "updates"
_VERSION_STATUS_STYLE = "bold #55FFA5"
_VERSION_METADATA_STYLE = "bold #FF85B3"


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
    #env-refresh {
        width: auto;
        height: auto;
        padding: 0 1 0 0;
        content-align: right middle;
        display: none;
    }
    #update-branch {
        height: 1;
        padding: 0 1;
        margin: 0 0 0 0;
        display: none;
    }
    """

    def __init__(
        self,
        *args,
        on_summary: Callable[[str], None] | None = None,
        on_result: Callable[[dict], None] | None = None,
        show_status: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._on_summary = on_summary
        self._on_result = on_result
        self._show_status = show_status

    def compose(self) -> ComposeResult:
        with Horizontal(id="update-row"):
            yield Static("[dim]Checking for updates…[/dim]", id="update-msg")
            yield Static("", id="env-refresh")
            yield Button("⬇ Pull update", id="btn-pull", variant="warning")
        yield Static("", id="update-branch")

    def on_mount(self) -> None:
        self.query_one("#btn-pull").display = False
        self.query_one("#update-msg").display = self._show_status
        self.query_one("#update-branch").display = False
        self.sync_visibility()
        cached = widget_cache.load_entry(_CACHE_KEY)
        if isinstance(cached, dict):
            self._apply(cached, from_cache=True)
        self.run_worker(self._check, thread=True, exclusive=True)

    def _check(self) -> None:
        result = check_for_updates()
        widget_cache.save_entry(_CACHE_KEY, result)
        self.app.call_from_thread(self._apply, result)

    def _set_message(self, message: str, *, summary: str | None = None) -> None:
        self.query_one("#update-msg", Static).update(message)
        if self._on_summary is not None:
            self._on_summary(summary or message.split("\n", 1)[0])

    def sync_visibility(self) -> None:
        """Collapse the row when this panel only publishes status to a parent."""
        if self._show_status:
            return
        row = self.query_one("#update-row", Horizontal)
        btn = self.query_one("#btn-pull", Button)
        refresh = self.query_one("#env-refresh", Static)
        row.display = bool(btn.display or refresh.display)

    def _apply(self, result: dict, from_cache: bool = False) -> None:
        btn = self.query_one("#btn-pull", Button)
        status = result["status"]
        # Never paint a stale "behind"/branch from cache — the cached entry may
        # reflect a different branch the checkout has since left. Show a neutral
        # placeholder and let the live check confirm.
        if from_cache and status != "up_to_date":
            self._set_message("[dim]Checking for updates…[/dim]")
            self.sync_visibility()
            return
        if self._on_result is not None:
            self._on_result(result)
        btn.display = False
        self.query_one("#update-branch").display = False
        if status == "up_to_date":
            date = result.get("date", "")
            date_suffix = f"  [{_VERSION_METADATA_STYLE}]{date}[/]" if date else ""
            self._set_message(
                f"[{_VERSION_STATUS_STYLE}]✓ Latest version[/]  "
                f"[{_VERSION_METADATA_STYLE}]{result['hash']}[/]{date_suffix}"
            )
        elif status == "behind":
            count = result.get("behind_count")
            subject = result.get("subject", "")
            count_str = f" ({count})" if count else ""
            subject_line = f"\n[dim]· {subject}[/dim]" if subject else ""
            summary = (
                f"[yellow bold]⬆ Update available{count_str}[/yellow bold]  "
                f"[dim]{result['local']} → {result['remote']}[/dim]"
            )
            self._set_message(
                f"[yellow bold]⬆ Update available{count_str}[/yellow bold]  "
                f"[dim]{result['local']} → {result['remote']}[/dim]"
                f"{subject_line}",
                summary=summary,
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
            self._set_message("[dim]branch has no upstream — updates not tracked[/dim]")
        elif status == "no_git":
            self._set_message("[dim]git not found — cannot check for updates[/dim]")
        else:
            self._set_message("[dim]⚠ Could not reach remote[/dim]")
        self.sync_visibility()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-pull":
            event.stop()
            self.query_one("#btn-pull").display = False
            self.query_one("#update-branch").display = False
            self._set_message("[yellow]Pulling…[/yellow]")
            self.sync_visibility()
            self.run_worker(self._pull, thread=True, exclusive=True)

    def _pull(self) -> None:
        ok, output = do_git_pull()

        def _done() -> None:
            if ok:
                self._set_message(
                    "[green]✓ Pulled — restart the wizard to apply changes[/green]"
                )
            else:
                self._set_message(
                    f"[red]✗ Pull failed:[/red] [dim]{output[:120]}[/dim]"
                )
                self.query_one("#btn-pull").display = True
            self.sync_visibility()

        self.app.call_from_thread(_done)
