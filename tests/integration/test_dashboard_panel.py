"""Pilot integration tests for DashboardPanel.

Foundational coverage: shadow-smoke mount (C-P-T5) and the select-a-project
placeholder with no workers started (C-P-T4). Later story phases append here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
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


def _cache_key_for(project: Path) -> str:
    import hashlib

    from cabal.widgets.dashboard_panel import CACHE_PREFIX

    digest = hashlib.sha1(str(project).encode("utf-8")).hexdigest()[:16]
    return f"{CACHE_PREFIX}{digest}"


def _seed_cache(project: Path, branch: str, supabase_ref: str = "CACHED_REF") -> None:
    from cabal.models.dashboard import (
        AvailabilityState,
        DashboardSnapshot,
        GitHubSection,
        GitSection,
        SupabaseSection,
        VercelSection,
    )

    snapshot = DashboardSnapshot(
        project_path=str(project),
        captured_at="2026-06-01T00:00:00+00:00",
        git=GitSection(state=AvailabilityState.OK, current_branch=branch),
        github=GitHubSection(state=AvailabilityState.NOT_AUTHED),
        supabase=SupabaseSection(state=AvailabilityState.OK, project_ref=supabase_ref),
        vercel=VercelSection(state=AvailabilityState.NOT_LINKED),
    )
    widget_cache.save_entry(_cache_key_for(project), snapshot.to_cacheable())


@pytest.mark.asyncio
async def test_panel_paints_cached_section_before_workers_finish(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal import dashboard_git_service

    _seed_cache(tmp_project_dir, "cached-branch-xyz", supabase_ref="CACHED_REF_42")
    gate = threading.Event()

    def blocked_collect_git(_project):
        gate.wait(timeout=5)
        from cabal.models.dashboard import AvailabilityState, GitSection

        return GitSection(state=AvailabilityState.OK, current_branch="live-branch")

    monkeypatch.setattr(dashboard_git_service, "collect_git", blocked_collect_git)
    app = _DashboardHost(selected_project=tmp_project_dir)

    try:
        async with app.run_test() as pilot:
            await pilot.pause()

            git_body = str(app.query_one("#dash-git", Static).render())

            assert "cached-branch-xyz" in git_body and "refreshing" not in git_body
    finally:
        gate.set()


@pytest.mark.asyncio
async def test_panel_isolates_failing_git_section_from_github(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal import dashboard_git_service, dashboard_github_service
    from cabal.models.dashboard import AvailabilityState, GitHubSection, GitSection

    monkeypatch.setattr(
        dashboard_git_service,
        "collect_git",
        lambda _project: GitSection(state=AvailabilityState.ERROR, hint="git blew up"),
    )
    monkeypatch.setattr(
        dashboard_github_service,
        "collect_github",
        lambda _project, _branch, _remotes: GitHubSection(
            state=AvailabilityState.OK, connected=True, owner_repo="o/r"
        ),
    )
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        git_body = await _settle_section(pilot, app, "#dash-git")
        github_body = await _settle_section(pilot, app, "#dash-github")

        assert "git blew up" in git_body and "o/r" in github_body


@pytest.mark.asyncio
async def test_panel_rescope_to_new_project_drops_previous_branch(
    isolated_cache, monkeypatch, tmp_path
):
    from cabal import dashboard_git_service
    from cabal.models.dashboard import AvailabilityState, GitSection

    project_a = tmp_path / "proj-a"
    project_b = tmp_path / "proj-b"
    project_a.mkdir()
    project_b.mkdir()
    branches = {str(project_a): "aaa", str(project_b): "bbb"}
    monkeypatch.setattr(
        dashboard_git_service,
        "collect_git",
        lambda project: GitSection(
            state=AvailabilityState.OK, current_branch=branches[str(project)]
        ),
    )

    app_a = _DashboardHost(selected_project=project_a)
    async with app_a.run_test() as pilot:
        await _settle_section(pilot, app_a, "#dash-git")

    app_b = _DashboardHost(selected_project=project_b)
    async with app_b.run_test() as pilot:
        body_b = await _settle_section(pilot, app_b, "#dash-git")

        assert "aaa" not in body_b and "bbb" in body_b


@pytest.mark.asyncio
async def test_panel_cache_file_never_contains_access_tokens(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal import dashboard_git_service, dashboard_github_service
    from cabal.models.dashboard import (
        AvailabilityState,
        GitHubSection,
        GitSection,
    )

    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_sentinel_supabase_999")
    monkeypatch.setenv("VERCEL_TOKEN", "vrc_sentinel_vercel_888")
    monkeypatch.setattr(
        dashboard_git_service,
        "collect_git",
        lambda _project: GitSection(state=AvailabilityState.OK, current_branch="main"),
    )
    monkeypatch.setattr(
        dashboard_github_service,
        "collect_github",
        lambda _project, _branch, _remotes: GitHubSection(
            state=AvailabilityState.OK, connected=True, owner_repo="o/r"
        ),
    )
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        await _settle_section(pilot, app, "#dash-git")
        await _settle_section(pilot, app, "#dash-github")
        cache_text = (isolated_cache / "cache.json").read_text(encoding="utf-8")

        assert "sentinel" not in cache_text


def _stub_supabase_section(monkeypatch, section) -> None:
    from cabal import dashboard_supabase_service

    monkeypatch.setattr(
        dashboard_supabase_service, "collect_supabase", lambda _project: section
    )


@pytest.mark.asyncio
async def test_panel_renders_supabase_baseline_ref(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal.models.dashboard import AvailabilityState, SupabaseSection

    section = SupabaseSection(
        state=AvailabilityState.OK,
        project_ref="abcdefgh",
        dashboard_url="https://supabase.com/dashboard/project/abcdefgh",
        schema_visualizer_url="https://supabase.com/dashboard/project/abcdefgh/database/schemas",
        db_location="db.abcdefgh.supabase.co",
        last_migration="0001_init",
        enrich_state=AvailabilityState.TOKEN_MISSING,
        enrich_hint="set SUPABASE_ACCESS_TOKEN for plan/region/members/backups",
    )
    _stub_supabase_section(monkeypatch, section)
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_section(pilot, app, "#dash-supabase")

        assert "abcdefgh" in body


@pytest.mark.asyncio
async def test_panel_renders_supabase_baseline_enrich_hint(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal.models.dashboard import AvailabilityState, SupabaseSection

    section = SupabaseSection(
        state=AvailabilityState.OK,
        project_ref="abcdefgh",
        dashboard_url="https://supabase.com/dashboard/project/abcdefgh",
        db_location="db.abcdefgh.supabase.co",
        last_migration="0001_init",
        enrich_state=AvailabilityState.TOKEN_MISSING,
        enrich_hint="set SUPABASE_ACCESS_TOKEN for plan/region/members/backups",
    )
    _stub_supabase_section(monkeypatch, section)
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_section(pilot, app, "#dash-supabase")

        assert "set SUPABASE_ACCESS_TOKEN" in body


@pytest.mark.asyncio
async def test_panel_renders_supabase_enriched_region(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal.models.dashboard import (
        AvailabilityState,
        ProjectMember,
        SupabaseSection,
    )

    section = SupabaseSection(
        state=AvailabilityState.OK,
        project_ref="abcdefgh",
        dashboard_url="https://supabase.com/dashboard/project/abcdefgh",
        db_location="db.abcdefgh.supabase.co",
        status="ACTIVE_HEALTHY",
        region="us-east-1",
        plan_name="pro",
        members=[ProjectMember(name="octocat", role="Owner")],
        enrich_state=AvailabilityState.OK,
    )
    _stub_supabase_section(monkeypatch, section)
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_section(pilot, app, "#dash-supabase")

        assert "us-east-1" in body


@pytest.mark.asyncio
async def test_panel_renders_supabase_not_linked_hint(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal.models.dashboard import AvailabilityState, SupabaseSection

    section = SupabaseSection(
        state=AvailabilityState.NOT_LINKED,
        hint="no linked Supabase project",
    )
    _stub_supabase_section(monkeypatch, section)
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_section(pilot, app, "#dash-supabase")

        assert "no linked Supabase project" in body


def _stub_vercel_section(monkeypatch, section) -> None:
    from cabal import dashboard_vercel_service

    monkeypatch.setattr(
        dashboard_vercel_service, "collect_vercel", lambda _project: section
    )


@pytest.mark.asyncio
async def test_panel_renders_vercel_baseline_enrich_hint(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal.models.dashboard import AvailabilityState, VercelSection

    section = VercelSection(
        state=AvailabilityState.OK,
        project_id="proj_1",
        enrich_state=AvailabilityState.TOKEN_MISSING,
        enrich_hint="set VERCEL_TOKEN for team/plan/region/members",
    )
    _stub_vercel_section(monkeypatch, section)
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_section(pilot, app, "#dash-vercel")

        assert "set VERCEL_TOKEN" in body


@pytest.mark.asyncio
async def test_panel_renders_vercel_enriched_deployment(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal.models.dashboard import (
        AvailabilityState,
        ProjectMember,
        VercelSection,
    )

    section = VercelSection(
        state=AvailabilityState.OK,
        project_id="proj_1",
        project_name="my-app",
        latest_deployment_status="READY",
        team_plan="pro",
        members=[ProjectMember(name="octocat", role="OWNER")],
        enrich_state=AvailabilityState.OK,
    )
    _stub_vercel_section(monkeypatch, section)
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_section(pilot, app, "#dash-vercel")

        assert "my-app" in body


@pytest.mark.asyncio
async def test_panel_renders_vercel_not_linked_hint(
    isolated_cache, tmp_project_dir, monkeypatch
):
    from cabal.models.dashboard import AvailabilityState, VercelSection

    section = VercelSection(
        state=AvailabilityState.NOT_LINKED,
        hint="no linked Vercel project",
    )
    _stub_vercel_section(monkeypatch, section)
    app = _DashboardHost(selected_project=tmp_project_dir)

    async with app.run_test() as pilot:
        body = await _settle_section(pilot, app, "#dash-vercel")

        assert "no linked Vercel project" in body
