# -*- coding: utf-8 -*-
"""Smoke tests for the OpenCode setup screen."""

from __future__ import annotations

from cabal.app import CabalApp
from cabal.opencode_setup.conversion import OpenCodeAsset
from cabal.opencode_setup.status import OpenCodeStatus
from cabal.views import opencode_setup as screen_module
from cabal.views.opencode_setup import OpenCodeSetupScreen
from textual.widgets import DataTable
from textual.widgets import Button

import pytest


def _write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _status() -> OpenCodeStatus:
    return OpenCodeStatus(
        cli=True,
        desktop_app=True,
        version="1.15.10",
        global_config=True,
        tui_config=True,
        skills_dir=True,
        tools_dir=True,
        codex_cli=True,
        codex_mcp_configured=True,
        claude_cli=True,
        gemini_cli=True,
        antigravity_cli=True,
    )


def _missing_status() -> OpenCodeStatus:
    return OpenCodeStatus(
        cli=False,
        desktop_app=False,
        version=None,
        global_config=True,
        tui_config=True,
        skills_dir=True,
        tools_dir=True,
        codex_cli=True,
        codex_mcp_configured=True,
        claude_cli=True,
        gemini_cli=True,
        antigravity_cli=True,
    )


@pytest.mark.asyncio
async def test_opencode_setup_screen_mounts(tmp_path, monkeypatch):
    source = tmp_path / "source" / "opencode.json"
    target = tmp_path / "target" / "opencode.json"
    _write(source, "{}")
    asset = OpenCodeAsset(
        key="config::opencode",
        label="opencode.json",
        source=source,
        target=target,
        state="NEW",
        group="config",
    )
    monkeypatch.setattr(screen_module, "opencode_status", lambda: _status())
    monkeypatch.setattr(screen_module, "build_global_plan", lambda: [asset])
    monkeypatch.setattr(screen_module, "build_project_plan", lambda _project: [])

    app = CabalApp()
    async with app.run_test() as pilot:
        screen = OpenCodeSetupScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#opencode-preview", DataTable).row_count == 1


@pytest.mark.asyncio
async def test_opencode_setup_screen_has_separate_cli_and_desktop_installs(monkeypatch):
    monkeypatch.setattr(screen_module, "opencode_status", lambda: _missing_status())
    monkeypatch.setattr(screen_module, "build_global_plan", lambda: [])
    monkeypatch.setattr(screen_module, "build_project_plan", lambda _project: [])

    app = CabalApp()
    async with app.run_test() as pilot:
        screen = OpenCodeSetupScreen()
        await app.push_screen(screen)
        await pilot.pause()

        cli = screen.query_one("#opencode-install-cli", Button)
        desktop = screen.query_one("#opencode-install-desktop", Button)
        assert str(cli.label) == "Install CLI"
        assert str(desktop.label) == "Install Desktop App"
        assert cli.display is True
        assert desktop.display is True
