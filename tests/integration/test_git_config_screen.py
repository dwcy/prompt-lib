"""Smoke tests for GitConfigScreen — scope toggle + agent commit policy editor.

Mount the screen through Textual's compose() pipeline so framework-shadow bugs
surface; exercise the policy save round-trip against a tmp ~/.claude.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal import git_policy
from cabal.app import CabalApp
from cabal.views.git_config import GitConfigScreen


@pytest.fixture
def tmp_policy_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    claude_dir = tmp_path / ".claude"
    user_file = claude_dir / "git-policy.json"
    default_file = claude_dir / "git" / "git-policy.default.json"
    monkeypatch.setattr(git_policy, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(git_policy, "POLICY_PATH", user_file)
    monkeypatch.setattr(git_policy, "POLICY_DEFAULT_PATH", default_file)
    return user_file


@pytest.mark.asyncio
async def test_git_config_screen_mounts_without_nameerror(tmp_policy_paths):
    app = CabalApp()
    async with app.run_test() as pilot:
        app.push_screen(GitConfigScreen())
        await pilot.pause()

        assert isinstance(app.screen, GitConfigScreen)


@pytest.mark.asyncio
async def test_policy_save_writes_user_file(tmp_policy_paths: Path):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = GitConfigScreen()
        app.push_screen(screen)
        await pilot.pause()

        from textual.widgets import Checkbox, Input

        screen.query_one("#pol-agent-name", Input).value = "Test Agent"
        screen.query_one("#pol-agent-email", Input).value = "test@example.com"
        screen.query_one("#pol-allowed-types", Input).value = "feat, wip"
        screen.query_one("#pol-refuse-branches", Input).value = "main"
        screen.query_one("#pol-may-tag", Checkbox).value = True
        screen.query_one("#pol-auto-push", Checkbox).value = False
        screen._save_policy()
        await pilot.pause()

        written = json.loads(tmp_policy_paths.read_text(encoding="utf-8"))

    assert written == {
        "agent_name": "Test Agent",
        "agent_email": "test@example.com",
        "allowed_types": ["feat", "wip"],
        "refuse_on_branches": ["main"],
        "tags": {"agent_may_tag": True, "auto_push": False},
    }


@pytest.mark.asyncio
async def test_local_scope_disabled_when_no_repo(
    tmp_policy_paths, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    app = CabalApp()
    async with app.run_test() as pilot:
        app.push_screen(GitConfigScreen())
        await pilot.pause()

        from textual.widgets import RadioButton

        local_radio = app.screen.query_one("#scope-local", RadioButton)

        assert local_radio.disabled is True


def test_split_csv_strips_and_drops_blanks():
    assert GitConfigScreen._split_csv(" feat ,  fix,, docs , ") == [
        "feat",
        "fix",
        "docs",
    ]
