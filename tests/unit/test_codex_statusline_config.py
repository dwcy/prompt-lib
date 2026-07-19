"""Focused tests for native Codex statusline configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from cabal import statusline_config


@pytest.fixture
def codex_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / ".codex" / "config.toml"
    monkeypatch.setattr(statusline_config, "CODEX_CONFIG_PATH", path)
    return path


def test_codex_catalog_contains_every_native_status_item():
    keys = {item["key"] for item in statusline_config.load_layout("codex")}

    assert len(keys - {"__use-theme-colors"}) == 26
    assert {"git-branch", "task-progress", "workspace-headline"} <= keys


def test_save_codex_layout_preserves_unrelated_config(codex_config: Path):
    codex_config.parent.mkdir(parents=True)
    codex_config.write_text(
        'model = "gpt-5.4"\n\n[tui]\nanimations = false\n'
        'status_line = ["model"]\n\n[features]\ngoals = true\n',
        encoding="utf-8",
    )
    layout = statusline_config.load_layout("codex")
    for item in layout:
        item["enabled"] = item["key"] in {
            "git-branch",
            "project-name",
            "__use-theme-colors",
        }

    statusline_config.save_layout(layout, "codex")
    parsed = tomllib.loads(codex_config.read_text(encoding="utf-8"))

    assert parsed["model"] == "gpt-5.4"
    assert parsed["features"]["goals"] is True
    assert parsed["tui"]["animations"] is False
    assert parsed["tui"]["status_line"] == ["git-branch", "project-name"]
    assert parsed["tui"]["status_line_use_colors"] is True


def test_enable_all_writes_all_native_items(codex_config: Path):
    layout = statusline_config.load_layout("codex")
    for item in layout:
        item["enabled"] = True

    statusline_config.save_layout(layout, "codex")
    parsed = tomllib.loads(codex_config.read_text(encoding="utf-8"))

    assert len(parsed["tui"]["status_line"]) == 26
    assert parsed["tui"]["status_line"][0] == "git-branch"
    assert parsed["tui"]["status_line_use_colors"] is True
