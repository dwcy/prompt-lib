"""Pilot smoke tests for EnvPanel + UpdatePanel stale-while-revalidate flow.

Covers: mount with no cache (placeholder shows), mount with seeded cache
(cached value paints immediately), worker completion updates the value and
writes cache.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from cabal import widget_cache
from cabal.widgets.env_panel import EnvPanel
from cabal.widgets.update_panel import UpdatePanel


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", tmp_path / "cache.json")
    yield tmp_path


class _UpdateHost(App):
    def compose(self) -> ComposeResult:
        yield UpdatePanel()


@pytest.mark.asyncio
async def test_update_panel_paints_cached_value_on_mount(isolated_cache, monkeypatch):
    from cabal.widgets import update_panel

    # Stub the live check so no real git/network worker runs and lingers to
    # pollute later tests' cache files.
    monkeypatch.setattr(
        update_panel,
        "check_for_updates",
        lambda: {"status": "up_to_date", "hash": "deadbeef", "date": "2026-01-01"},
    )
    widget_cache.save_entry(
        "updates",
        {"status": "up_to_date", "hash": "deadbeef", "date": "2026-01-01"},
    )

    app = _UpdateHost()
    async with app.run_test() as pilot:
        await pilot.pause()
        msg = app.query_one("#update-msg", Static)

        plain = str(msg.render())

        assert "deadbeef" in plain


@pytest.mark.asyncio
async def test_update_panel_worker_writes_cache(isolated_cache, monkeypatch):
    from cabal.widgets import update_panel

    monkeypatch.setattr(
        update_panel,
        "check_for_updates",
        lambda: {"status": "up_to_date", "hash": "abc12345", "date": "2026-06-01"},
    )

    app = _UpdateHost()
    async with app.run_test() as pilot:
        await pilot.pause()
        cached = None
        for _ in range(20):
            await pilot.pause()
            entry = widget_cache.load_entry("updates")
            # Wait for THIS panel's worker result, not a stray write from a
            # leftover worker of a prior test (which may lack a "hash" key).
            if isinstance(entry, dict) and entry.get("hash") == "abc12345":
                cached = entry
                break

        assert cached is not None
        assert cached["hash"] == "abc12345"


class _EnvHost(App):
    # EnvPanel._update_paths reads app.selected_project — mirror CabalApp's attr.
    selected_project = None

    def compose(self) -> ComposeResult:
        yield EnvPanel()


_FAKE_ENV: dict = {
    "os": "Linux",
    "release": "6.1.0",
    "python": "3.11.1",
    "shell": "/bin/bash",
    "pkg_manager": "apt-get",
    "git": True,
    "git_user": "Tester",
    "git_version": "git version 2.45.0",
    "gh_login": None,
    "bash": True,
    "claude": True,
    "gh": True,
    "node": "v22.0.0",
    "npm": "10.0.0",
    "pnpm": None,
    "bun": None,
    "dotnet": None,
    "dotnet_sdks": [],
    "docker": None,
    "podman": None,
    "kubectl": None,
    "terraform": None,
    "az": None,
    "gcloud": None,
    "aws": None,
    "gemini": False,
    "codex": False,
    "opencode": False,
    "grok": False,
    "cursor": False,
    "windsurf": False,
    "copilot": False,
    "antigravity": False,
    "vscode": True,
    "rider": False,
    "visualstudio": False,
    "ollama": False,
    "ollama_models": [],
    "sqlcmd": False,
    "psql": False,
    "supabase": False,
    "neonctl": False,
    "target_exists": True,
}


@pytest.mark.asyncio
async def test_env_panel_uses_cached_env_on_mount(isolated_cache, monkeypatch):
    widget_cache.save_entry("env", _FAKE_ENV)
    from cabal.widgets import env_panel, update_panel

    monkeypatch.setattr(env_panel, "detect_env", lambda: _FAKE_ENV)
    monkeypatch.setattr(update_panel, "check_for_updates", lambda: {"status": "no_git"})

    app = _EnvHost()
    async with app.run_test() as pilot:
        await pilot.pause()

        os_cells = [str(s.render()) for s in app.query("#env-row-system Static")]

        assert any("Linux" in t for t in os_cells)


@pytest.mark.asyncio
async def test_env_panel_worker_writes_cache(isolated_cache, monkeypatch):
    from cabal.widgets import env_panel, update_panel

    monkeypatch.setattr(env_panel, "detect_env", lambda: _FAKE_ENV)
    monkeypatch.setattr(update_panel, "check_for_updates", lambda: {"status": "no_git"})

    app = _EnvHost()
    async with app.run_test() as pilot:
        for _ in range(30):
            await pilot.pause()
            cached = widget_cache.load_entry("env")
            if cached:
                break

        assert cached is not None
        assert cached["os"] == "Linux"
