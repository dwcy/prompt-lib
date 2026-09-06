"""Tests for safe terminal settings and shell profile discovery."""

from __future__ import annotations

import json
from pathlib import Path

from cabal.webapi import terminal_service


def test_strip_jsonc_preserves_urls_and_removes_comments_and_trailing_commas() -> None:
    source = """
    {
      // generated settings
      "$schema": "https://aka.ms/terminal-profiles-schema",
      "profiles": {"list": [{"name": "PowerShell",},],},
    }
    """

    parsed = json.loads(terminal_service._strip_jsonc(source))

    assert parsed["$schema"] == "https://aka.ms/terminal-profiles-schema"
    assert parsed["profiles"]["list"][0]["name"] == "PowerShell"


def test_terminal_modifications_reports_settings_without_returning_profile_content(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    profile_path = tmp_path / "profile.ps1"
    profile_path.write_text(
        'oh-my-posh init pwsh | Invoke-Expression\nSet-Alias gs "git status"\n',
        encoding="utf-8",
    )
    settings = {
        "schemes": [{"name": "Custom"}],
        "actions": [{"command": "copy"}],
        "profiles": {},
    }

    modifications = terminal_service._terminal_modifications(
        settings_path,
        settings,
        [{"name": "PowerShell", "font": {"face": "Cascadia Code"}}],
        {},
        [profile_path],
    )
    labels = {item["label"] for item in modifications}

    assert {"Profiles", "Color schemes", "Key bindings", "Fonts"} <= labels
    assert {"Shell profile", "Oh My Posh", "Custom aliases"} <= labels
    serialized = json.dumps(modifications)
    assert "Invoke-Expression" not in serialized
    assert "git status" not in serialized
