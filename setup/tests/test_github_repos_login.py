# -*- coding: utf-8 -*-
"""GitHubReposScreen login callback behavior."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.css.query import NoMatches
from textual.widgets import Button, Static

from cabal import gh_accounts
from cabal.views.github_repos import GitHubReposScreen


@pytest.mark.asyncio
async def test_refresh_and_back_buttons_are_not_rendered(monkeypatch):
    monkeypatch.setattr(GitHubReposScreen, "action_refresh", lambda self: None)

    app = App()
    async with app.run_test() as pilot:
        screen = GitHubReposScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#gh-repos-clone", Button)
        assert screen.query_one("#gh-repos-login", Button)
        assert screen.query_one("#gh-repos-accounts", Button)
        with pytest.raises(NoMatches):
            screen.query_one("#gh-repos-refresh", Button)
        with pytest.raises(NoMatches):
            screen.query_one("#gh-repos-back", Button)


@pytest.mark.asyncio
async def test_logged_out_only_shows_login_button(monkeypatch):
    monkeypatch.setattr(GitHubReposScreen, "action_refresh", lambda self: None)

    app = App()
    async with app.run_test() as pilot:
        screen = GitHubReposScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen._set_logged_out()

        assert screen.query_one("#gh-repos-login", Button).display is True
        assert screen.query_one("#gh-repos-clone", Button).display is False
        assert screen.query_one("#gh-repos-accounts", Button).display is False


@pytest.mark.asyncio
async def test_loaded_repos_restore_clone_and_accounts_buttons(monkeypatch):
    monkeypatch.setattr(GitHubReposScreen, "action_refresh", lambda self: None)

    app = App()
    async with app.run_test() as pilot:
        screen = GitHubReposScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen._set_logged_out()
        screen._set_repos([])

        assert screen.query_one("#gh-repos-login", Button).display is False
        assert screen.query_one("#gh-repos-clone", Button).display is True
        assert screen.query_one("#gh-repos-accounts", Button).display is True


@pytest.mark.asyncio
async def test_login_registers_device_token_before_refresh(monkeypatch):
    tokens: list[str] = []
    refreshes: list[bool] = []

    def fake_register(token: str, host: str = "github.com") -> tuple[bool, str]:
        tokens.append(token)
        return True, "account added"

    def fake_refresh(self: GitHubReposScreen) -> None:
        refreshes.append(True)

    monkeypatch.setattr(gh_accounts, "add_account_with_token", fake_register)
    monkeypatch.setattr(GitHubReposScreen, "action_refresh", fake_refresh)

    app = App()
    async with app.run_test() as pilot:
        screen = GitHubReposScreen()
        await app.push_screen(screen)
        await pilot.pause()
        refreshes.clear()

        screen._on_login("token-123")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert tokens == ["token-123"]
        assert refreshes == [True]
        assert app.env_needs_refresh is True


@pytest.mark.asyncio
async def test_account_modal_change_marks_overview_for_refresh(monkeypatch):
    refreshes: list[bool] = []

    def fake_refresh(self: GitHubReposScreen) -> None:
        refreshes.append(True)

    monkeypatch.setattr(GitHubReposScreen, "action_refresh", fake_refresh)

    app = App()
    async with app.run_test() as pilot:
        screen = GitHubReposScreen()
        await app.push_screen(screen)
        await pilot.pause()
        refreshes.clear()

        screen._after_accounts_closed(True)

        assert app.env_needs_refresh is True
        assert refreshes == [True]


@pytest.mark.asyncio
async def test_unchanged_account_modal_does_not_refresh_overview(monkeypatch):
    refreshes: list[bool] = []

    def fake_refresh(self: GitHubReposScreen) -> None:
        refreshes.append(True)

    monkeypatch.setattr(GitHubReposScreen, "action_refresh", fake_refresh)

    app = App()
    async with app.run_test() as pilot:
        screen = GitHubReposScreen()
        await app.push_screen(screen)
        await pilot.pause()
        refreshes.clear()

        screen._after_accounts_closed(False)

        assert getattr(app, "env_needs_refresh", False) is False
        assert refreshes == []


@pytest.mark.asyncio
async def test_login_registration_failure_stays_visible(monkeypatch):
    def fake_register(token: str, host: str = "github.com") -> tuple[bool, str]:
        return False, "bad credentials"

    monkeypatch.setattr(GitHubReposScreen, "action_refresh", lambda self: None)
    monkeypatch.setattr(gh_accounts, "add_account_with_token", fake_register)

    app = App()
    async with app.run_test() as pilot:
        screen = GitHubReposScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen._on_login("token-123")
        await app.workers.wait_for_complete()
        await pilot.pause()

        status = screen.query_one("#gh-repos-status", Static)
        assert "bad credentials" in str(status.render())
