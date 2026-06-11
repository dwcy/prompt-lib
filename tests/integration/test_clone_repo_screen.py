"""Smoke tests for the Clone-existing-repo flow (CloneRepoScreen + GitHubReposScreen).

Mounting through Textual's compose() pipeline is what catches missing module-level
names and DOM-id mismatches; the actual `gh repo clone` subprocess is never invoked
here (no network).
"""

from __future__ import annotations

import platform
from pathlib import Path

import pytest

from cabal.app import CabalApp
from cabal.views.clone_repo import CloneRepoScreen, default_projects_dir
from cabal.views.github_repos import GitHubReposScreen
from cabal.views.project_gate import ProjectGateScreen


@pytest.mark.asyncio
async def test_clone_repo_screen_mounts_in_choose_phase():
    app = CabalApp()
    async with app.run_test() as pilot:
        app.push_screen(CloneRepoScreen("octocat/hello", "hello"))
        await pilot.pause()

        assert isinstance(app.screen, CloneRepoScreen)
        assert app.screen.query_one("#clone-choose").display is True
        assert app.screen.query_one("#clone-run").display is False
        target = str(app.screen.query_one("#clone-target").render())
        assert "hello" in target


@pytest.mark.asyncio
async def test_github_repos_clone_without_selection_is_noop():
    app = CabalApp()
    async with app.run_test() as pilot:
        app.push_screen(GitHubReposScreen())
        await pilot.pause()
        screen = app.screen
        screen._repos = []

        screen.action_clone()
        await pilot.pause()

        assert isinstance(app.screen, GitHubReposScreen)
        status = str(screen.query_one("#gh-repos-status").render())
        assert "Select a repo" in status


def test_default_projects_dir_per_os():
    expected = Path("C:/projects") if platform.system() == "Windows" else Path.home() / "projects"

    assert default_projects_dir() == expected


def test_github_repos_requests_name_with_owner():
    import inspect

    src = inspect.getsource(GitHubReposScreen)

    assert "nameWithOwner" in src
    assert "gh-repos-login" in src


@pytest.mark.asyncio
async def test_project_gate_has_clone_button():
    app = CabalApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        assert isinstance(app.screen, ProjectGateScreen)
        clone_btn = app.screen.query_one("#gate-clone")
        assert "Clone" in str(clone_btn.label)


def test_github_repos_accepts_clone_callback():
    captured = {}

    screen = GitHubReposScreen(on_clone_done=lambda p: captured.setdefault("p", p))

    assert screen._on_clone_done is not None
