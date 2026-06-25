"""Local AI tool detection tests."""

from __future__ import annotations

import cabal.env_detect as env_detect


def test_opencode_cli_and_desktop_status_are_separate(monkeypatch):
    monkeypatch.setattr(env_detect.shutil, "which", lambda name: "opencode.cmd" if name == "opencode" else None)
    monkeypatch.setattr(env_detect, "_has_opencode_desktop", lambda: False)

    assert env_detect._opencode_status() == "CLI installed; desktop app not detected"

    monkeypatch.setattr(env_detect.shutil, "which", lambda name: None)
    monkeypatch.setattr(env_detect, "_has_opencode_desktop", lambda: True)

    assert env_detect._opencode_status() == "desktop app installed; CLI missing"

    monkeypatch.setattr(env_detect.shutil, "which", lambda name: "opencode.cmd" if name == "opencode" else None)
    monkeypatch.setattr(env_detect, "_has_opencode_desktop", lambda: True)

    assert env_detect._opencode_status() == "CLI and desktop app"
