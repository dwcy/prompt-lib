# -*- coding: utf-8 -*-
"""Tests for the Claude settings catalog + global/local read-merge and the screen."""

from __future__ import annotations

import json

import pytest
from textual.widgets import Checkbox

from cabal import claude_settings as cs
from cabal.app import CabalApp
from cabal.views.settings import SettingsScreen


def _def(key):
    return next(sd for sd in cs.CATALOG if sd.key == key)


def test_effective_value_prefers_local_then_global_then_default():
    sd = _def("autoCompactEnabled")

    assert cs.effective_value(sd, {}, {}) is True
    assert cs.effective_value(sd, {"autoCompactEnabled": False}, {}) is False
    assert (
        cs.effective_value(
            sd, {"autoCompactEnabled": False}, {"autoCompactEnabled": True}
        )
        is True
    )


def test_write_local_merges_and_preserves_existing_keys(tmp_path):
    target = cs.local_settings_path(tmp_path)
    target.parent.mkdir(parents=True)
    target.write_text(
        '{"permissions": {"allow": ["Bash(pytest:*)"]}}', encoding="utf-8"
    )

    cs.write_local(tmp_path, "remoteControlAtStartup", False)

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["remoteControlAtStartup"] is False
    assert data["permissions"]["allow"] == ["Bash(pytest:*)"]


def test_write_local_creates_file_when_absent(tmp_path):
    cs.write_local(tmp_path, "verbose", True)

    data = json.loads(cs.local_settings_path(tmp_path).read_text(encoding="utf-8"))
    assert data == {"verbose": True}


def test_reset_local_removes_only_catalog_keys(tmp_path):
    target = cs.local_settings_path(tmp_path)
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps({"verbose": True, "permissions": {"allow": []}}), encoding="utf-8"
    )

    removed = cs.reset_local(tmp_path)

    data = json.loads(target.read_text(encoding="utf-8"))
    assert removed == 1
    assert "verbose" not in data
    assert data["permissions"] == {"allow": []}


def test_read_global_falls_back_to_repo_source(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "TARGET", tmp_path / "no-claude")
    repo_global = tmp_path / "global"
    repo_global.mkdir()
    (repo_global / "settings.json").write_text('{"verbose": true}', encoding="utf-8")
    monkeypatch.setattr(cs, "GLOBAL_DIR", repo_global)

    assert cs.read_global() == {"verbose": True}


@pytest.mark.asyncio
async def test_settings_screen_mount_does_not_write_local(tmp_path):
    app = CabalApp()
    app.selected_project = tmp_path

    async with app.run_test() as pilot:
        screen = SettingsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#set-remoteControlAtStartup", Checkbox) is not None
        assert screen.query_one("#set-verbose", Checkbox) is not None

    assert not cs.local_settings_path(tmp_path).exists()


@pytest.mark.asyncio
async def test_settings_screen_toggle_writes_local_override(tmp_path):
    app = CabalApp()
    app.selected_project = tmp_path

    async with app.run_test() as pilot:
        screen = SettingsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        cb = screen.query_one("#set-remoteControlAtStartup", Checkbox)
        cb.toggle()
        await pilot.pause()

    data = json.loads(cs.local_settings_path(tmp_path).read_text(encoding="utf-8"))
    assert "remoteControlAtStartup" in data
