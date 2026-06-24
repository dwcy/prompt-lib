# -*- coding: utf-8 -*-
"""GitHubReposScreen login callback behavior."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Static

from cabal import gh_accounts
from cabal.views.github_repos import GitHubReposScreen


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
