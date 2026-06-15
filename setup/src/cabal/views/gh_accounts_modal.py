# -*- coding: utf-8 -*-
"""GhAccountsModal — list, switch, add, re-auth, and forget gh CLI accounts."""

from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from cabal import gh_accounts
from cabal.gh_accounts import GhAccount
from cabal.installers.gh import gh_device_init
from cabal.views.gh_device import GhDeviceFlowScreen

_DEVICE_SCOPES = ["repo", "read:org", "gist", "workflow"]

# gh prefers these env vars over the active account; switching while one is
# exported looks like it "did nothing" in any shell that sets it.
_TOKEN_OVERRIDE_VARS = ("GH_TOKEN", "GITHUB_TOKEN")


class GhAccountsModal(ModalScreen[bool]):
    """Manage gh CLI accounts for github.com.

    Dismisses with True if anything changed (switch / add / forget), so the
    caller knows to refresh env state.
    """

    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    GhAccountsModal { align: center middle; }
    GhAccountsModal #gha-box {
        width: 76;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: round #FF55A5;
        padding: 1 2;
    }
    GhAccountsModal #gha-title { text-style: bold; margin: 0 0 1 0; }
    GhAccountsModal #gha-warn { height: auto; margin: 0 0 1 0; }
    GhAccountsModal .gha-row { height: 3; margin: 0 0 1 0; }
    GhAccountsModal .gha-label { width: 1fr; content-align: left middle; height: 3; }
    GhAccountsModal .gha-row Button { margin: 0 0 0 1; min-width: 10; }
    GhAccountsModal #gha-status { margin: 1 0 0 0; height: auto; }
    GhAccountsModal #gha-actions { height: 3; margin: 1 0 0 0; align: right middle; }
    GhAccountsModal #gha-actions Button { margin: 0 0 0 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._accounts: list[GhAccount] = []
        self._changed = False
        self._confirm_forget: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="gha-box"):
            yield Static("GitHub Accounts — github.com", id="gha-title")
            yield Static("", id="gha-warn")
            yield Vertical(id="gha-list")
            yield Static("", id="gha-status")
            with Horizontal(id="gha-actions"):
                yield Button("Add account", id="gha-add", variant="primary")
                yield Button("Close (Esc)", id="gha-close")

    def on_mount(self) -> None:
        override = next((v for v in _TOKEN_OVERRIDE_VARS if os.environ.get(v)), None)
        if override:
            self.query_one("#gha-warn", Static).update(
                f"[yellow]⚠ {override} is set in this environment — gh ignores the "
                f"active account while it is exported, so switching will appear to "
                f"have no effect in shells that set it.[/yellow]"
            )
        self._reload()

    # -- loading -----------------------------------------------------------

    def _reload(self) -> None:
        self._set_status("[dim]Loading accounts…[/dim]")
        self.run_worker(self._load_accounts, thread=True, exclusive=True)

    def _load_accounts(self) -> None:
        accounts = gh_accounts.list_accounts()
        self.app.call_from_thread(self._show_accounts, accounts)

    def _show_accounts(self, accounts: list[GhAccount]) -> None:
        if not self.is_mounted:
            return
        self._accounts = accounts
        lst = self.query_one("#gha-list", Vertical)
        lst.remove_children()
        if not accounts:
            lst.mount(
                Static(
                    "[dim]No gh CLI accounts — use Add account to log in.[/dim]",
                    classes="gha-label",
                )
            )
        for i, acc in enumerate(accounts):
            lst.mount(self._account_row(i, acc))
        self._set_status("")

    def _account_row(self, i: int, acc: GhAccount) -> Horizontal:
        if not acc.valid:
            label = f"[red]✗[/red] [b]{acc.user}[/b] [red](invalid token)[/red]"
        elif acc.active:
            store = acc.storage or "stored"
            label = f"[green]●[/green] [b]{acc.user}[/b] [dim](active, {store})[/dim]"
        else:
            label = f"[dim]○[/dim] {acc.user}"
        widgets = [Static(label, classes="gha-label")]
        if acc.valid and not acc.active:
            widgets.append(Button("Switch", id=f"gha-switch-{i}", variant="success"))
        if not acc.valid:
            widgets.append(Button("Re-auth", id=f"gha-reauth-{i}", variant="warning"))
        if not acc.active:
            widgets.append(Button("Forget", id=f"gha-forget-{i}", variant="error"))
        return Horizontal(*widgets, classes="gha-row")

    # -- operations ---------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid != f"gha-forget-{self._index_of(self._confirm_forget)}":
            self._confirm_forget = None
        if bid == "gha-close":
            self.action_close()
        elif bid == "gha-add":
            self._start_device_flow()
        elif bid.startswith("gha-switch-"):
            self._run_op(gh_accounts.switch_account, self._user_for(bid))
        elif bid.startswith("gha-reauth-"):
            self._start_device_flow()
        elif bid.startswith("gha-forget-"):
            user = self._user_for(bid)
            if self._confirm_forget == user:
                self._confirm_forget = None
                self._run_op(gh_accounts.forget_account, user)
            else:
                self._confirm_forget = user
                self._set_status(
                    f"[yellow]Press Forget again to remove [b]{user}[/b].[/yellow]"
                )

    def _index_of(self, user: str | None) -> int:
        for i, acc in enumerate(self._accounts):
            if acc.user == user:
                return i
        return -1

    def _user_for(self, bid: str) -> str:
        i = int(bid.rsplit("-", 1)[1])
        return self._accounts[i].user

    def _run_op(self, op, user: str) -> None:
        self._set_status(f"[dim]Working on {user}…[/dim]")

        def work() -> None:
            ok, msg = op(user)
            self.app.call_from_thread(self._after_op, ok, msg)

        self.run_worker(work, thread=True, exclusive=True)

    def _after_op(self, ok: bool, msg: str) -> None:
        if not self.is_mounted:
            return
        if ok:
            self._changed = True
            self._reload()
        else:
            self._set_status(f"[red]✗ {msg}[/red]")

    # -- add / re-auth via device flow ---------------------------------------

    def _start_device_flow(self) -> None:
        self._set_status("[dim]Starting GitHub device flow…[/dim]")

        def init() -> None:
            device = gh_device_init(_DEVICE_SCOPES)
            self.app.call_from_thread(self._open_device_modal, device)

        self.run_worker(init, thread=True, exclusive=True)

    def _open_device_modal(self, device: dict | None) -> None:
        if not self.is_mounted:
            return
        if not device:
            self._set_status("[red]✗ Could not start the device flow (network?)[/red]")
            return
        self._set_status("")
        self.app.push_screen(GhDeviceFlowScreen(device), self._token_received)

    def _token_received(self, token: str | None) -> None:
        if not token:
            self._set_status("[yellow]Login cancelled.[/yellow]")
            return
        self._set_status("[dim]Registering account with gh…[/dim]")

        def register() -> None:
            ok, msg = gh_accounts.add_account_with_token(token)
            self.app.call_from_thread(self._after_op, ok, msg)

        self.run_worker(register, thread=True, exclusive=True)

    # -- misc ----------------------------------------------------------------

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#gha-status", Static).update(text)
        except Exception:
            pass

    def action_close(self) -> None:
        self.dismiss(self._changed)
