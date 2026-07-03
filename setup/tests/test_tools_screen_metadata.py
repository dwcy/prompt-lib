# -*- coding: utf-8 -*-
"""Tools screen metadata rendering tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Button, Select, Static

import cabal.views.tools as tools_view
from cabal import widget_cache
from cabal.installers import dotnet_releases
from cabal.views.tools import ToolsScreen


@pytest.fixture(autouse=True)
def _disable_tools_workers(monkeypatch):
    monkeypatch.setattr(ToolsScreen, "on_mount", lambda self: None)


@pytest.mark.asyncio
async def test_tools_screen_renders_descriptions():
    app = App()
    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        name = screen.query_one("#tool-name-git", Static)
        assert "version control" in str(name.tooltip).lower()


@pytest.mark.asyncio
async def test_tools_screen_renders_read_more_actions():
    app = App()
    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        source = screen.query_one("#tool-source-zed", Button)
        assert str(source.label) == "Read more"
        assert source.disabled is False


@pytest.mark.asyncio
async def test_read_more_uses_source_url(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(tools_view.webbrowser, "open", lambda url: opened.append(url))
    app = App()

    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()
        button = screen.query_one("#tool-source-zed", Button)
        screen.on_button_pressed(type("Pressed", (), {"button": button})())
        await pilot.pause()

        assert opened == ["https://zed.dev/"]
        assert "https://zed.dev/" in str(
            screen.query_one("#tools-status", Static).content
        )


@pytest.mark.asyncio
async def test_source_required_row_disables_install_button():
    app = App()
    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        install = screen.query_one("#tool-install-hermes-agent", Button)
        source = screen.query_one("#tool-source-hermes-agent", Button)
        assert install.disabled is True
        assert source.disabled is True
        assert str(source.label) == "Source req"


@pytest.mark.asyncio
async def test_version_selector_renders_for_runtime_tools():
    app = App()
    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#tool-version-node", Select) is not None


@pytest.fixture
def isolated_dotnet_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", tmp_path / "cache.json")


@pytest.mark.asyncio
async def test_compose_never_triggers_dotnet_releases_network_fetch(
    isolated_dotnet_cache, monkeypatch
):
    def fail_fetch(timeout=dotnet_releases._FETCH_TIMEOUT):
        raise AssertionError("compose()/version_options_for must never fetch over the network")

    monkeypatch.setattr(dotnet_releases, "_fetch_releases_index", fail_fetch)
    app = App()

    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#tool-version-dotnet", Select) is not None


@pytest.mark.asyncio
async def test_background_worker_refresh_populates_real_dotnet_versions(
    isolated_dotnet_cache, monkeypatch
):
    release_index = [
        {
            "channel-version": "10.0",
            "support-phase": "active",
            "release-type": "lts",
            "latest-sdk": "10.0.100",
        },
    ]
    calls = {"count": 0}

    def fake_fetch(timeout=dotnet_releases._FETCH_TIMEOUT):
        calls["count"] += 1
        return release_index

    monkeypatch.setattr(dotnet_releases, "_fetch_releases_index", fake_fetch)
    app = App()

    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen.run_worker(
            screen._refresh_dotnet_version_select, thread=True, exclusive=False
        )
        await app.workers.wait_for_complete()
        await pilot.pause()

        select = screen.query_one("#tool-version-dotnet", Select)
        assert calls["count"] == 1
        assert "10.0.100" in select._legal_values
