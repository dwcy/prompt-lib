"""Contract tests for the project/overview/dashboard endpoints and the
project.select action-safety flow of specs/015-web-ui-overhaul/contracts/web-api.contract.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from .webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]

SCHEMA_VERSION = "cabal-web.v2"
MODULE_READ_ROUTES = ("/api/project", "/api/overview", "/api/dashboard?section=git")
DASHBOARD_SECTIONS = ("git", "github", "supabase", "vercel")
OVERVIEW_SECTION_KEYS = {
    "dashboard_summary",
    "recent_sessions",
    "account",
    "doctor",
    "knowledge_availability",
    "security_summary",
    "drift_flags",
}
PROJECT_CONTEXT_KEYS = {"path", "name", "is_git_repo", "recents", "selected_at"}
EFFECT_PREVIEW_KEYS = {"summary", "commands", "files_changed", "scopes", "backup", "removals"}


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


def _envelope_shape_ok(body: dict) -> bool:
    return bool(
        body.get("schema_version") == SCHEMA_VERSION
        and body.get("status") in {"ok", "degraded", "error"}
        and body.get("captured_at")
        and body.get("source")
        and isinstance(body.get("stale"), bool)
        and "precondition_digest" in body
        and "data" in body
        and "error" in body
    )


def test_Project_get_returns_v2_envelope_with_context_shape(app_factory, tmp_path: Path) -> None:
    project_dir = tmp_path / "myproj"
    project_dir.mkdir()
    _app, client = build_client(app_factory, project=project_dir)

    response = client.get("/api/project", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    data = body["data"]
    assert PROJECT_CONTEXT_KEYS <= set(data)
    assert data["path"] == str(project_dir)
    assert data["name"] == "myproj"
    assert data["is_git_repo"] is False
    assert isinstance(data["recents"], list)


def test_Project_get_reports_is_git_repo_true_for_a_git_project(app_factory, tmp_path: Path) -> None:
    project_dir = tmp_path / "gitproj"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    _app, client = build_client(app_factory, project=project_dir)

    response = client.get("/api/project", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["data"]["is_git_repo"] is True


def test_Project_get_recents_prunes_dead_paths_and_returns_recent_project_shape(
    app_factory, tmp_path: Path
) -> None:
    from cabal import recent_projects

    live_dir = tmp_path / "live-project"
    live_dir.mkdir()
    dead_dir = tmp_path / "dead-project"
    dead_dir.mkdir()
    recent_projects.record_recent(dead_dir, "open")
    recent_projects.record_recent(live_dir, "open")
    dead_dir.rmdir()
    _app, client = build_client(app_factory, project=live_dir)

    response = client.get("/api/project", headers=auth_headers())

    assert response.status_code == 200
    recents = response.json()["data"]["recents"]
    recent_paths = {item["path"] for item in recents}
    assert str(live_dir) in recent_paths
    assert str(dead_dir) not in recent_paths
    for item in recents:
        assert {"path", "name", "action", "last_opened"} <= set(item)


def test_ProjectSelect_prepare_returns_ticket_with_effect_preview_and_digest(
    app_factory, tmp_path: Path
) -> None:
    origin = tmp_path / "origin-project"
    origin.mkdir()
    target = tmp_path / "target-project"
    target.mkdir()
    _app, client = build_client(app_factory, project=origin)

    response = client.post(
        "/api/actions/project.select/prepare",
        json={"path": str(target)},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    ticket = response.json()["data"]
    assert ticket["action_id"] == "project.select"
    assert ticket["ticket_id"]
    assert ticket["precondition_digest"]
    preview = ticket["effect_preview"]
    assert EFFECT_PREVIEW_KEYS <= set(preview)
    assert preview["summary"]


def test_ProjectSelect_execute_switches_project_context_and_records_one_audit_entry(
    app_factory, tmp_path: Path
) -> None:
    origin = tmp_path / "origin-project"
    origin.mkdir()
    target = tmp_path / "target-project"
    target.mkdir()
    _app, client = build_client(app_factory, project=origin)
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
    context = client.get("/api/project", headers=auth_headers())
    assert context.json()["data"]["path"] == str(target)
    audit = client.get("/api/audit", headers=auth_headers())
    matching = [e for e in audit.json()["data"]["entries"] if e["ticket_id"] == ticket["ticket_id"]]
    assert len(matching) == 1
    assert matching[0]["outcome"] == "succeeded"


def test_ProjectSelect_prepare_missing_path_param_returns_422(app_factory, tmp_path: Path) -> None:
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.post("/api/actions/project.select/prepare", json={}, headers=auth_headers())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "params_invalid"


def test_ProjectSelect_prepare_nonexistent_path_returns_422(app_factory, tmp_path: Path) -> None:
    _app, client = build_client(app_factory, project=tmp_path)
    missing = tmp_path / "does-not-exist"

    response = client.post(
        "/api/actions/project.select/prepare",
        json={"path": str(missing)},
        headers=auth_headers(),
    )

    assert response.status_code == 422


def test_ProjectSelect_execute_without_prepare_returns_404_or_409(app_factory, tmp_path: Path) -> None:
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.post(
        "/api/actions/project.select/execute",
        json={"ticket_id": "never-prepared-ticket-id"},
        headers=auth_headers(),
    )

    assert response.status_code in {404, 409}


def test_Overview_get_returns_v2_envelope_with_home_payload_sections(app_factory, tmp_path: Path) -> None:
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.get("/api/overview", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    assert OVERVIEW_SECTION_KEYS <= set(body["data"])


def test_Overview_drift_flags_reports_claude_and_codex_booleans(app_factory, tmp_path: Path) -> None:
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.get("/api/overview", headers=auth_headers())

    drift_flags = response.json()["data"]["drift_flags"]
    assert isinstance(drift_flags["claude"], bool)
    assert isinstance(drift_flags["codex"], bool)


@pytest.mark.parametrize("section", DASHBOARD_SECTIONS)
def test_Dashboard_get_section_returns_v2_envelope_with_stale_flag(
    app_factory, tmp_path: Path, section: str
) -> None:
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.get(f"/api/dashboard?section={section}", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    assert body["data"] is not None


def test_Dashboard_missing_section_query_param_returns_422(app_factory, tmp_path: Path) -> None:
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.get("/api/dashboard", headers=auth_headers())

    assert response.status_code == 422


def test_Dashboard_unknown_section_value_returns_422(app_factory, tmp_path: Path) -> None:
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.get("/api/dashboard?section=bogus", headers=auth_headers())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "params_invalid"


@pytest.mark.parametrize("path", MODULE_READ_ROUTES)
def test_ModuleRoute_missing_bearer_token_returns_401(app_factory, path: str) -> None:
    _app, client = build_client(app_factory)

    response = client.get(path)

    assert response.status_code == 401
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"
    assert body["data"] is None


@pytest.mark.parametrize("path", MODULE_READ_ROUTES)
def test_ModuleRoute_wrong_bearer_token_returns_401(app_factory, path: str) -> None:
    _app, client = build_client(app_factory)

    response = client.get(path, headers=auth_headers("wrong-token"))

    assert response.status_code == 401


@pytest.mark.parametrize("path", MODULE_READ_ROUTES)
@pytest.mark.parametrize("method", ("POST", "PUT", "PATCH", "DELETE"))
def test_ModuleRoute_mutating_verb_returns_405(app_factory, path: str, method: str) -> None:
    _app, client = build_client(app_factory)

    response = client.request(method, path, headers=auth_headers())

    assert response.status_code == 405
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"
    assert body["data"] is None
