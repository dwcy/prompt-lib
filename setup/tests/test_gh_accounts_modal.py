# -*- coding: utf-8 -*-
"""Smoke tests for GhAccountsModal — render, switch, forget-confirm."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button, Static

from cabal import gh_accounts
from cabal.gh_accounts import GhAccount
from cabal.views.gh_accounts_modal import GhAccountsModal

ACCOUNTS = [
    GhAccount("dwcy", "github.com", active=True, valid=True, storage="keyring"),
    GhAccount("other", "github.com", active=False, valid=True, storage="keyring"),
    GhAccount("stale", "github.com", active=False, valid=False, storage="hosts.yml"),
]


async def _settle(app: App, pilot) -> None:
    await app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.asyncio
async def test_renders_account_rows_with_expected_buttons(monkeypatch):
    monkeypatch.setattr(
        gh_accounts, "list_accounts", lambda host="github.com": ACCOUNTS
    )
    app = App()
    async with app.run_test() as pilot:
        modal = GhAccountsModal()
        await app.push_screen(modal)
        await _settle(app, pilot)

        ids = {b.id for b in modal.query(Button)}
        assert "gha-switch-1" in ids  # valid inactive → Switch
        assert "gha-reauth-2" in ids  # invalid → Re-auth
        assert "gha-forget-2" in ids
        assert "gha-switch-0" not in ids  # active account has no Switch
        assert "gha-forget-0" not in ids
        assert str(modal.query_one("#gha-add", Button).label) == "Add account"


@pytest.mark.asyncio
async def test_no_accounts_show_login_button(monkeypatch):
    monkeypatch.setattr(gh_accounts, "list_accounts", lambda host="github.com": [])
    app = App()
    async with app.run_test() as pilot:
        modal = GhAccountsModal()
        await app.push_screen(modal)
        await _settle(app, pilot)

        assert str(modal.query_one("#gha-add", Button).label) == "Login to GitHub"


@pytest.mark.asyncio
async def test_switch_calls_service_and_reloads(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        gh_accounts, "list_accounts", lambda host="github.com": ACCOUNTS
    )

    def fake_switch(user, host="github.com"):
        calls.append(user)
        return True, "switched"

    monkeypatch.setattr(gh_accounts, "switch_account", fake_switch)
    app = App()
    async with app.run_test() as pilot:
        modal = GhAccountsModal()
        await app.push_screen(modal)
        await _settle(app, pilot)

        modal.query_one("#gha-switch-1", Button).press()
        await _settle(app, pilot)
        await _settle(app, pilot)  # reload worker after the op

        assert calls == ["other"]
        assert modal._changed is True


@pytest.mark.asyncio
async def test_token_env_override_warning(monkeypatch):
    monkeypatch.setattr(
        gh_accounts, "list_accounts", lambda host="github.com": ACCOUNTS
    )
    monkeypatch.setenv("GH_TOKEN", "ghp_dummy")
    app = App()
    async with app.run_test() as pilot:
        modal = GhAccountsModal()
        await app.push_screen(modal)
        await _settle(app, pilot)
        assert "GH_TOKEN" in str(modal.query_one("#gha-warn", Static).render())


@pytest.mark.asyncio
async def test_no_warning_without_token_env(monkeypatch):
    monkeypatch.setattr(
        gh_accounts, "list_accounts", lambda host="github.com": ACCOUNTS
    )
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    app = App()
    async with app.run_test() as pilot:
        modal = GhAccountsModal()
        await app.push_screen(modal)
        await _settle(app, pilot)
        assert str(modal.query_one("#gha-warn", Static).render()).strip() == ""


@pytest.mark.asyncio
async def test_forget_requires_second_press(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        gh_accounts, "list_accounts", lambda host="github.com": ACCOUNTS
    )

    def fake_forget(user, host="github.com"):
        calls.append(user)
        return True, "removed"

    monkeypatch.setattr(gh_accounts, "forget_account", fake_forget)
    app = App()
    async with app.run_test() as pilot:
        modal = GhAccountsModal()
        await app.push_screen(modal)
        await _settle(app, pilot)

        modal.query_one("#gha-forget-2", Button).press()
        await _settle(app, pilot)
        assert calls == []  # first press only arms the confirm
        status = modal.query_one("#gha-status", Static)
        assert "stale" in str(status.render())

        modal.query_one("#gha-forget-2", Button).press()
        await _settle(app, pilot)
        await _settle(app, pilot)

        assert calls == ["stale"]


@pytest.mark.asyncio
async def test_add_account_registers_device_token_and_marks_changed(monkeypatch):
    tokens: list[str] = []
    monkeypatch.setattr(
        gh_accounts, "list_accounts", lambda host="github.com": ACCOUNTS
    )

    def fake_add(token: str, host: str = "github.com") -> tuple[bool, str]:
        tokens.append(token)
        return True, "account added"

    monkeypatch.setattr(gh_accounts, "add_account_with_token", fake_add)
    app = App()
    async with app.run_test() as pilot:
        modal = GhAccountsModal()
        await app.push_screen(modal)
        await _settle(app, pilot)
        modal._reload = lambda: None

        modal._token_received("token-456")
        await _settle(app, pilot)

        assert tokens == ["token-456"]
        assert modal._changed is True
