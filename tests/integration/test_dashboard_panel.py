"""Pilot integration tests for DashboardPanel.

Foundational coverage: shadow-smoke mount (C-P-T5) and the select-a-project
placeholder with no workers started (C-P-T4). Later story phases append here.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from cabal import widget_cache
from cabal.widgets.dashboard_panel import DashboardPanel

SECTION_IDS = ("#dash-git", "#dash-github", "#dash-supabase", "#dash-vercel")


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", tmp_path / "cache.json")
    yield tmp_path


class _DashboardHost(App):
    def __init__(self, selected_project) -> None:
        super().__init__()
        self.selected_project = selected_project
        self.project_path = selected_project

    def compose(self) -> ComposeResult:
        yield DashboardPanel(id="dashboard")


@pytest.mark.asyncio
async def test_panel_mounts_without_shadow_crash(isolated_cache, tmp_project_dir):
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        await pilot.pause()

        panel = app.query_one("#dashboard", DashboardPanel)

        assert panel.is_mounted


@pytest.mark.asyncio
async def test_panel_renders_all_four_section_bodies(isolated_cache, tmp_project_dir):
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        await pilot.pause()

        bodies = [app.query_one(section_id, Static) for section_id in SECTION_IDS]

        assert len(bodies) == 4


@pytest.mark.asyncio
async def test_panel_shows_placeholder_when_no_project(isolated_cache):
    app = _DashboardHost(selected_project=None)

    async with app.run_test() as pilot:
        await pilot.pause()

        git_body = str(app.query_one("#dash-git", Static).render())

        assert "select a project" in git_body


@pytest.mark.asyncio
async def test_panel_starts_no_workers_when_no_project(isolated_cache):
    app = _DashboardHost(selected_project=None)

    async with app.run_test() as pilot:
        await pilot.pause()

        panel = app.query_one("#dashboard", DashboardPanel)

        assert len(panel.workers) == 0


def _init_git_repo(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-b", "main", str(path)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test User"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "remote",
            "add",
            "origin",
            "https://github.com/o/r.git",
        ],
        check=True,
        capture_output=True,
    )


async def _settle_section(pilot, app, section_id: str) -> str:
    for _ in range(50):
        body = str(app.query_one(section_id, Static).render())
        if "refreshing" not in body and "loading" not in body:
            return body
        await pilot.pause()
    return str(app.query_one(section_id, Static).render())


async def _settle_git_section(pilot, app) -> str:
    return await _settle_section(pilot, app, "#dash-git")


@pytest.mark.asyncio
async def test_panel_renders_branch_for_real_repo(isolated_cache, tmp_project_dir):
    if shutil.which("git") is None:
        pytest.skip("git CLI not available")
    _init_git_repo(tmp_project_dir)
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_git_section(pilot, app)

        assert "main" in body


@pytest.mark.asyncio
async def test_panel_shows_not_a_git_repository_hint(isolated_cache, tmp_project_dir):
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_git_section(pilot, app)

        assert "not a git repository" in body


def _stub_github_section(monkeypatch, section) -> None:
    from cabal import dashboard_git_service, dashboard_github_service
    from cabal.models.dashboard import AvailabilityState, GitSection

    monkeypatch.setattr(
        dashboard_git_service,
        "collect_git",
        lambda _project: GitSection(state=AvailabilityState.OK, current_branch="main"),
    )
    monkeypatch.setattr(
        dashboard_github_service,
        "collect_github",
        lambda _project, _branch, _remotes: section,
    )


@pytest.mark.asyncio
async def test_panel_renders_github_runs_and_prs(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal.models.dashboard import (
        AvailabilityState,
        GitHubSection,
        PullRequest,
        WorkflowRun,
    )

    section = GitHubSection(
        state=AvailabilityState.OK,
        connected=True,
        owner_repo="o/r",
        remote_used="origin",
        runs=[
            WorkflowRun(
                name="CI",
                branch="main",
                status="completed",
                conclusion="success",
                url="https://x/run/1",
                created_at="2026-06-01",
            )
        ],
        pull_requests=[
            PullRequest(
                number=7,
                title="Add dashboard panel",
                author="octocat",
                url="https://x/pr/7",
            )
        ],
    )
    _stub_github_section(monkeypatch, section)
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_section(pilot, app, "#dash-github")

        assert "Add dashboard panel" in body


@pytest.mark.asyncio
async def test_panel_renders_github_run_conclusion(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal.models.dashboard import AvailabilityState, GitHubSection, WorkflowRun

    section = GitHubSection(
        state=AvailabilityState.OK,
        connected=True,
        owner_repo="o/r",
        remote_used="origin",
        runs=[
            WorkflowRun(
                name="CI",
                branch="main",
                status="completed",
                conclusion="success",
                url="https://x/run/1",
                created_at="2026-06-01",
            )
        ],
    )
    _stub_github_section(monkeypatch, section)
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_section(pilot, app, "#dash-github")

        assert "success" in body


@pytest.mark.asyncio
async def test_panel_shows_github_unauth_hint(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal.models.dashboard import AvailabilityState, GitHubSection

    section = GitHubSection(
        state=AvailabilityState.NOT_AUTHED,
        owner_repo="o/r",
        remote_used="origin",
        hint="not authenticated — run `gh auth login`",
    )
    _stub_github_section(monkeypatch, section)
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_section(pilot, app, "#dash-github")

        assert "gh auth login" in body
