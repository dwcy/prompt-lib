"""Contract tests for the project/overview/dashboard endpoints and the
project.select action-safety flow of specs/015-web-ui-overhaul/contracts/web-api.contract.md."""

from __future__ import annotations

import json
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


def _write_session(projects_dir: Path, session_id: str, timestamp: str) -> None:
    project_dir = projects_dir / "prompt-lib"
    project_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "type": "assistant",
        "timestamp": timestamp,
        "gitBranch": "015-web-ui-overhaul",
        "message": {
            "role": "assistant",
            "model": "claude-sonnet-4-5",
            "content": [{"type": "text", "text": f"Session {session_id}"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    }
    (project_dir / f"{session_id}.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")


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


def test_ServiceLogs_unknown_key_returns_404_without_resolving_arbitrary_path(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/services/not-a-service/logs", headers=auth_headers())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "service_not_found"


def test_ServiceLogStream_keeps_monotonic_ids_after_log_truncation(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal import service_supervisor
    from cabal.webapi.routers import services as services_router

    log_dir = tmp_path / "service-logs"
    monkeypatch.setattr(service_supervisor, "_LOG_DIR", log_dir)
    services_router._LOG_STATES.clear()
    log_path = service_supervisor.log_path("a2a-bridge")
    log_path.write_text("first run\n", encoding="utf-8")
    _app, client = build_client(app_factory)
    headers = {**auth_headers(), "Accept": "text/event-stream"}

    first = client.get("/api/services/a2a-bridge/logs/stream", headers=headers)
    assert first.status_code == 200
    assert "id: 0" in first.text
    assert "first run" in first.text

    log_path.write_text("second run\n", encoding="utf-8")
    second = client.get(
        "/api/services/a2a-bridge/logs/stream",
        headers={**headers, "Last-Event-ID": "0"},
    )

    assert second.status_code == 200
    assert "id: 1" in second.text
    assert "second run" in second.text


def test_KnowledgeGraph_paginates_nodes_without_dropping_cross_page_edges(
    app_factory, tmp_path: Path
) -> None:
    project = tmp_path / "knowledge-project"
    bundle = project / "docs" / "okf" / "prompt-lib"
    bundle.mkdir(parents=True)
    nodes = [
        {"id": f"node:{index:02d}", "type": "agent", "label": f"Node {index:02d}"}
        for index in range(26)
    ]
    graph = {
        "generated_at": "2026-07-19T10:00:00Z",
        "nodes": nodes,
        "edges": [
            {
                "id": "cross-page",
                "source": "node:00",
                "target": "node:25",
                "kind": "delegates_to",
            }
        ],
    }
    (bundle / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    _app, client = build_client(app_factory, project=project)

    first = client.get("/api/knowledge/graph?limit=25", headers=auth_headers()).json()["data"]
    second = client.get(
        f"/api/knowledge/graph?limit=25&cursor={first['next_cursor']}",
        headers=auth_headers(),
    ).json()["data"]

    assert len(first["nodes"]) == 25
    assert first["edges"] == [
        {
            "id": "cross-page",
            "from": "node:00",
            "to": "node:25",
            "target_ref": "node:25",
            "relation": "delegates_to",
            "confidence": "",
            "reason": "",
            "evidence": [],
        }
    ]
    assert [node["id"] for node in second["nodes"]] == ["node:25"]
    assert second["next_cursor"] is None
    assert second["total_nodes"] == 26
    assert second["total_edges"] == 1


def test_Sessions_contract_paginates_with_stable_totals_and_lazy_tabs(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal import session_reader

    projects_dir = tmp_path / "sessions"
    _write_session(projects_dir, "session-a", "2026-07-19T10:00:00Z")
    _write_session(projects_dir, "session-b", "2026-07-19T11:00:00Z")
    monkeypatch.setattr(session_reader, "_PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(session_reader, "_WRITE_AUDIT_PATH", tmp_path / "write-audit.jsonl")
    _app, client = build_client(app_factory)

    first = client.get("/api/sessions?limit=1", headers=auth_headers()).json()["data"]
    second = client.get(
        f"/api/sessions?limit=1&cursor={first['next_cursor']}", headers=auth_headers()
    ).json()["data"]

    assert first["totals"]["session_count"] == 2
    assert len(first["items"]) == len(second["items"]) == 1
    assert first["items"][0]["session_id"] != second["items"][0]["session_id"]
    assert second["next_cursor"] is None
    session_id = first["items"][0]["session_id"]
    for tab in ("overview", "activity", "raw", "triggers"):
        detail = client.get(
            f"/api/sessions/{session_id}?tab={tab}", headers=auth_headers()
        )
        assert detail.status_code == 200
        assert detail.json()["data"]["tab"] == tab
        assert detail.json()["data"]["session_id"] == session_id


def test_Account_observability_routes_return_their_contract_shapes(
    app_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.webapi.routers import account as account_router

    monkeypatch.setattr(
        account_router,
        "account_payload",
        lambda: {"authenticated": False, "identity": None, "credential_sources": []},
    )
    monkeypatch.setattr(
        account_router,
        "doctor_payload",
        lambda _project: {
            "findings": [],
            "counts": {"error": 0, "warning": 0},
            "from_cache": False,
            "checked_target": "fixture",
            "project": None,
        },
    )
    monkeypatch.setattr(
        account_router,
        "models_payload",
        lambda: {
            "assignments": [],
            "assignable_models": ["haiku", "sonnet", "opus"],
            "counts": {"total": 0, "invalid": 0, "out_of_sync": 0},
        },
    )
    monkeypatch.setattr(
        account_router,
        "claude_info_payload",
        lambda _project: {"documents": [], "runtime": {"python": "3.14", "platform": "test", "project": None}},
    )
    _app, client = build_client(app_factory)

    expected = {
        "/api/account": {"authenticated", "identity", "credential_sources"},
        "/api/doctor": {"findings", "counts", "from_cache", "checked_target", "project"},
        "/api/models": {"assignments", "assignable_models", "counts"},
        "/api/claude-info": {"documents", "runtime"},
    }
    for path, keys in expected.items():
        response = client.get(path, headers=auth_headers())
        assert response.status_code == 200, path
        assert keys <= set(response.json()["data"]), path


def test_Knowledge_routes_report_honest_missing_and_semantic_unavailable_states(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.okf import semantic

    project = tmp_path / "knowledge-empty"
    project.mkdir()
    _app, client = build_client(app_factory, project=project)

    expected_keys = {
        "/api/knowledge": {"available", "counts", "semantic_available", "digest"},
        "/api/knowledge/graph": {"available", "nodes", "edges", "next_cursor"},
        "/api/knowledge/search?q=fixture": {"available", "status", "results"},
        "/api/knowledge/context-pack?q=fixture": {"available", "status", "pack"},
        "/api/knowledge/preflight?task=fixture": {"task", "report"},
        "/api/knowledge/usage": {"entries", "usage_path", "total_entries"},
    }
    for path, keys in expected_keys.items():
        response = client.get(path, headers=auth_headers())
        assert response.status_code == 200, path
        assert keys <= set(response.json()["data"]), path

    index = project / ".cabal" / "okf" / "index.sqlite"
    index.parent.mkdir(parents=True)
    index.touch()
    monkeypatch.setattr(semantic, "semantic_available", lambda: False)
    # knowledge_service imported the callable directly; patch that binding too.
    from cabal.webapi import knowledge_service

    monkeypatch.setattr(knowledge_service, "semantic_available", lambda: False)
    semantic_response = client.get(
        "/api/knowledge/search?q=fixture&mode=semantic", headers=auth_headers()
    )

    assert semantic_response.status_code == 200
    semantic_data = semantic_response.json()["data"]
    assert semantic_data["available"] is False
    assert semantic_data["status"] == "semantic_unavailable"
    assert semantic_data["results"] == []


def test_Mcp_and_service_routes_return_operational_contract_shapes(
    app_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.webapi.routers import mcp as mcp_router
    from cabal.webapi.routers import services as services_router

    server = {
        "name": "fixture-mcp",
        "scopes": ["user"],
        "status": "connected",
        "active": True,
        "pending": False,
        "command": "fixture-mcp",
        "env_required": [],
        "env_status": [],
        "env_present": True,
        "is_plugin": False,
        "plugin_id": None,
        "plugin_enabled": None,
        "plugin_scope": None,
        "removable_scopes": ["user"],
        "actions_available": ["disable"],
        "global_action_label": "Activate globally",
    }
    monkeypatch.setattr(
        mcp_router,
        "list_mcp_payload",
        lambda _state: {
            "servers": [server],
            "counts": {"total": 1, "connected": 1, "pending": 0, "inactive": 0, "error": 0},
            "project_dir": None,
        },
    )
    monkeypatch.setattr(
        mcp_router,
        "mcp_row_payload",
        lambda _state, _name: {"server": server, "project_dir": None},
    )
    monkeypatch.setattr(mcp_router, "mcp_digest", lambda _state, _name=None: "sha256:mcp")
    service = {
        "key": "fixture",
        "label": "Fixture service",
        "state": "stopped",
        "prereqs": [{"key": "python", "ok": True, "message": "ready"}],
        "log_stream_available": True,
    }
    monkeypatch.setattr(
        services_router,
        "services_payload",
        lambda: {
            "services": [service],
            "counts": {"total": 1, "running": 0, "stopped": 1, "not_set_up": 0, "blocked": 0},
        },
    )
    monkeypatch.setattr(services_router, "services_digest", lambda _key=None: "sha256:services")
    _app, client = build_client(app_factory)

    mcp_list = client.get("/api/mcp", headers=auth_headers())
    mcp_status = client.get("/api/mcp/fixture-mcp/status", headers=auth_headers())
    services = client.get("/api/services", headers=auth_headers())

    assert mcp_list.status_code == mcp_status.status_code == services.status_code == 200
    assert mcp_list.json()["data"]["servers"][0]["name"] == "fixture-mcp"
    assert mcp_status.json()["data"]["server"]["status"] == "connected"
    assert services.json()["data"]["services"][0]["prereqs"][0]["ok"] is True


def test_Provider_and_init_routes_cover_login_states_repos_templates_and_plan(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.init_project_service import LocalTemplateRef
    from cabal.webapi.routers import projects as projects_router

    monkeypatch.setattr(projects_router.gh_accounts, "list_accounts", lambda *_args: [])
    monkeypatch.setattr(projects_router, "gh_status", lambda: {"available": True})
    monkeypatch.setattr(
        projects_router,
        "_list_repos",
        lambda q=None, limit=100: [
            {
                "name": "prompt-lib",
                "owner": "fixture",
                "full_name": "fixture/prompt-lib",
                "visibility": "private",
                "updated_at": "2026-07-19T10:00:00Z",
                "url": "https://github.com/fixture/prompt-lib",
                "description": q or "fixture",
            }
        ][:limit],
    )
    template_file = tmp_path / "fixture-template.md"
    template_file.write_text("# Fixture project\n", encoding="utf-8")
    template_ref = LocalTemplateRef(stem="fixture", path=template_file)
    monkeypatch.setattr(projects_router, "_local_template_refs", lambda: [template_ref])
    monkeypatch.setattr(projects_router, "list_user_templates", lambda: [])
    _app, client = build_client(app_factory)

    for state in ("idle", "code_issued", "polling", "authenticated", "expired"):
        _app.state.provider_login_session = None if state == "idle" else {
            "state": state,
            "user_code": "ABCD-1234",
            "verification_uri": "https://github.com/login/device",
            "expires_at": 12345,
            "scopes": ["repo"],
            "message": state,
        }
        response = client.get("/api/provider", headers=auth_headers())
        assert response.status_code == 200
        assert response.json()["data"]["login"]["state"] == state

    repos = client.get("/api/provider/repos?q=prompt&limit=10", headers=auth_headers())
    templates = client.get("/api/init/templates", headers=auth_headers())
    plan = client.get(
        "/api/init/plan",
        params={"dest": str(tmp_path), "name": "new-project", "template": "local:fixture"},
        headers=auth_headers(),
    )

    assert repos.status_code == templates.status_code == plan.status_code == 200
    assert repos.json()["data"]["repos"][0]["full_name"] == "fixture/prompt-lib"
    assert templates.json()["data"]["local"][0]["id"] == "local:fixture"
    plan_data = plan.json()["data"]
    assert plan_data["name_valid"] is True
    assert plan_data["destination"] == str(tmp_path / "new-project")
    assert any(row["rel_path"] == "CLAUDE.md" for row in plan_data["staged_files"])


def test_Security_environment_and_git_routes_return_contract_shapes(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.webapi.routers import environment as environment_router
    from cabal.webapi.routers import security_scan as security_router

    monkeypatch.setattr(
        security_router,
        "_scan_payload",
        lambda project, refresh=False: (
            {
                "project": str(project),
                "scanned_at": "2026-07-19T10:00:00Z",
                "cached": not refresh,
                "ecosystems": ["python"],
                "findings": [],
                "outcomes": [],
                "notices": [],
                "summary": {"total": 0, "fixable": 0, "by_severity": {}, "by_ecosystem": {}},
            },
            not refresh,
        ),
    )
    monkeypatch.setattr(security_router, "security_digest", lambda _project: "sha256:security")
    monkeypatch.setattr(
        environment_router,
        "_curated_entries",
        lambda _q=None: [
            {
                "name": "PROJECTS_PATH",
                "value_redacted": str(tmp_path),
                "default": "",
                "is_path": True,
                "source": "default",
                "editable": True,
                "description": "Projects root",
            }
        ],
    )
    monkeypatch.setattr(environment_router, "env_digest", lambda: "sha256:env")
    monkeypatch.setattr(
        environment_router,
        "_identity_payload",
        lambda _state: {"repo_root": str(tmp_path), "identities": []},
    )
    monkeypatch.setattr(environment_router, "identity_digest", lambda _state: "sha256:identity")
    monkeypatch.setattr(
        environment_router,
        "_policy_payload",
        lambda: {"policy": {}, "source": "fixture", "defaults": {}},
    )
    monkeypatch.setattr(environment_router, "policy_digest", lambda: "sha256:policy")
    _app, client = build_client(app_factory, project=tmp_path)

    expected = {
        "/api/security/scan": {"project", "findings", "summary", "notices"},
        "/api/env": {"scope", "entries", "count", "editable_count", "platform"},
        "/api/git/identity": {"repo_root", "identities"},
        "/api/git/policy": {"policy", "source", "defaults"},
    }
    for path, keys in expected.items():
        response = client.get(path, headers=auth_headers())
        assert response.status_code == 200, path
        assert keys <= set(response.json()["data"]), path
