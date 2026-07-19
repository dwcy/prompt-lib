"""Integration tests for project-switch cache scoping and per-section overview degradation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from contract.webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]


@pytest.fixture(autouse=True)
def _isolate_file_backed_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect the real ~/.cabal recents/cache stores so tests never touch user data."""
    from cabal import recent_projects, widget_cache

    recents_dir = tmp_path / "recents-store"
    monkeypatch.setattr(recent_projects, "_DIR", recents_dir)
    monkeypatch.setattr(recent_projects, "_FILE", recents_dir / "recent_projects.json")

    cache_dir = tmp_path / "widget-cache-store"
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", cache_dir)
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", cache_dir / "cache.json")


def _init_git_repo(path: Path, branch: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", branch], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


def _switch_project(client, target: Path) -> None:
    prepared = client.post(
        "/api/actions/project.select/prepare",
        json={"path": str(target)},
        headers=auth_headers(),
    )
    assert prepared.status_code == 200
    ticket = prepared.json()["data"]

    executed = client.post(
        "/api/actions/project.select/execute",
        json={"ticket_id": ticket["ticket_id"]},
        headers=auth_headers(),
    )
    assert executed.status_code == 200


def test_ProjectSwitch_dashboard_git_section_reflects_new_project_not_stale_cache(
    app_factory, tmp_path: Path
) -> None:
    project_a = tmp_path / "project-a"
    _init_git_repo(project_a, "feature-a")
    project_b = tmp_path / "project-b"
    project_b.mkdir()
    _app, client = build_client(app_factory, project=project_a)

    before_switch = client.get("/api/dashboard?section=git", headers=auth_headers())
    _switch_project(client, project_b)
    after_switch = client.get("/api/dashboard?section=git", headers=auth_headers())

    assert before_switch.json()["data"]["current_branch"] == "feature-a"
    assert after_switch.json()["data"]["current_branch"] is None
    assert after_switch.json()["data"]["state"] == "not_linked"


def test_ProjectSwitch_dashboard_cache_entries_are_keyed_per_project_not_shared(
    app_factory, tmp_path: Path
) -> None:
    from cabal import widget_cache

    project_a = tmp_path / "project-a"
    _init_git_repo(project_a, "feature-a")
    project_b = tmp_path / "project-b"
    project_b.mkdir()
    _app, client = build_client(app_factory, project=project_a)

    client.get("/api/dashboard?section=git", headers=auth_headers())
    _switch_project(client, project_b)
    client.get("/api/dashboard?section=git", headers=auth_headers())

    cache_data = json.loads(widget_cache._CACHE_FILE.read_text(encoding="utf-8"))
    git_keys = [key for key in cache_data["entries"] if key.startswith("webapi-dashboard:git:")]

    assert len(git_keys) == 2


def test_ProjectSwitch_overview_dashboard_summary_reflects_new_project_not_stale_cache(
    app_factory, tmp_path: Path
) -> None:
    project_a = tmp_path / "project-a"
    _init_git_repo(project_a, "feature-a")
    project_b = tmp_path / "project-b"
    project_b.mkdir()
    _app, client = build_client(app_factory, project=project_a)

    client.get("/api/overview", headers=auth_headers())
    _switch_project(client, project_b)
    after_switch = client.get("/api/overview", headers=auth_headers())

    summary = after_switch.json()["data"]["dashboard_summary"]
    assert summary["project_path"] == str(project_b)
    assert summary["sections"]["git"]["current_branch"] is None


def test_Overview_get_degrades_account_section_when_gh_lookup_raises(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.webapi import overview_service

    project = tmp_path / "project"
    _init_git_repo(project, "main")
    _app, client = build_client(app_factory, project=project)

    def _boom() -> None:
        raise RuntimeError("gh CLI unavailable")

    monkeypatch.setattr(overview_service, "list_accounts", _boom)

    response = client.get("/api/overview", headers=auth_headers())
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "degraded"
    assert body["error"] is not None
    assert body["data"]["account"] == {"authenticated": False, "active_account": None, "accounts": []}


def test_Overview_get_keeps_sibling_sections_populated_when_account_section_fails(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.webapi import overview_service

    project = tmp_path / "project"
    _init_git_repo(project, "main")
    _app, client = build_client(app_factory, project=project)

    def _boom() -> None:
        raise RuntimeError("gh CLI unavailable")

    monkeypatch.setattr(overview_service, "list_accounts", _boom)

    response = client.get("/api/overview", headers=auth_headers())
    data = response.json()["data"]

    assert data["dashboard_summary"]["sections"]["git"]["current_branch"] == "main"


def test_Overview_get_returns_ok_status_with_null_error_when_no_collector_fails(
    app_factory, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    _init_git_repo(project, "main")
    _app, client = build_client(app_factory, project=project)

    response = client.get("/api/overview", headers=auth_headers())
    body = response.json()

    assert body["status"] == "ok"
    assert body["error"] is None
