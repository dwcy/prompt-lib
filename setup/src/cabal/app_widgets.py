# -*- coding: utf-8 -*-
"""Shared header + commands provider used by every screen and the CabalApp.

`AppHeader` swaps Textual's default icon for the CABAL ▼ menu indicator.
`AppCommandsProvider` is wired into `CabalApp.COMMANDS`, exposing the
home-screen actions through the header dropdown.
"""

from __future__ import annotations

from textual.command import DiscoveryHit, Hits, Provider
from textual.widgets import Header
from textual.widgets._header import HeaderIcon


class AppCommandsProvider(Provider):
    """Header dropdown — same bottom-bar actions plus Quit. No search."""

    async def discover(self) -> Hits:
        # Lazy imports so circular cabal.views.* → cabal.app_widgets doesn't load.
        from cabal.views.readme import ReadmeScreen
        from cabal.views.env import EnvScreen
        from cabal.views.git_config import GitConfigScreen
        from cabal.views.global_env import GlobalEnvScreen

        app = self.app
        yield DiscoveryHit(
            "README",
            lambda: app.push_screen(ReadmeScreen()),
            help="View the prompt-lib README",
        )
        yield DiscoveryHit(
            "Env vars",
            lambda: app.push_screen(EnvScreen()),
            help="Edit the curated env vars used by skills/hooks",
        )
        yield DiscoveryHit(
            "Git config",
            lambda: app.push_screen(GitConfigScreen()),
            help="View and edit your global git config (user.name, user.email)",
        )
        yield DiscoveryHit(
            "GitHub",
            app.open_github_accounts,
            help="Manage gh accounts for github.com",
        )
        yield DiscoveryHit(
            "All env",
            lambda: app.push_screen(GlobalEnvScreen()),
            help="Browse every environment variable on this machine",
        )
        from cabal.views.sessions import SessionsScreen

        yield DiscoveryHit(
            "Sessions",
            lambda: app.push_screen(SessionsScreen()),
            help="Browse Claude Code sessions — usage, cost, agents, skills",
        )
        yield DiscoveryHit(
            "Quit",
            app.action_quit,
            help="Exit the wizard",
        )

    async def search(self, query: str) -> Hits:
        return
        yield  # type: ignore[unreachable]  # keep this an async generator


class AppHeader(Header):
    def on_mount(self) -> None:
        icon = self.query_one(HeaderIcon)
        icon.icon = "▼"
        icon.tooltip = "Menu"
