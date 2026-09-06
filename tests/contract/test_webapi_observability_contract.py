"""Contract tests for US4 observability endpoints:
/api/sessions, /api/sessions/{id}, /api/account, /api/doctor, /api/models,
/api/claude-info, plus confirmation-gated session deletion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]

SCHEMA_VERSION = "cabal-web.v2"

OBSERVABILITY_READ_ROUTES = (
    "/api/sessions",
    "/api/account",
    "/api/doctor",
    "/api/models",
    "/api/claude-info",
)

SESSION_KEYS = {
    "session_id",
    "project",
    "branch",
    "started_at",
    "duration_seconds",
    "cost_usd",
    "tokens_in",
    "tokens_out",
    "agent_count",
    "skill_count",
    "tool_count",
    "files_written",
    "has_raw_log",
}
TOTAL_KEYS = {"session_count", "tokens_in", "tokens_out", "cost_usd", "duration_seconds"}
MODEL_KEYS = {
    "asset_kind",
    "asset_name",
    "pinned_model",
    "assignable_models",
    "repo_and_target_in_sync",
    "valid",
}


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


def _write_session(project_dir: Path, session_id: str, *, started: str = "2026-01-01T00:00:00Z") -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / f"{session_id}.jsonl"
    rows = [
        {
            "type": "user",
            "timestamp": started,
            "content": "/review src/app.py",
            "gitBranch": "feature/ui",
            "cwd": str(project_dir),
        },
        {
            "type": "assistant",
            "timestamp": "2026-01-01T00:00:10Z",
            "model": "claude-sonnet-4-6",
            "requestId": f"{session_id}-r1",
            "usage": {"input_tokens": 1200, "output_tokens": 400},
            "name": "Read",
            "input": {"file_path": "src/app.py"},
        },
        {
            "type": "assistant",
            "timestamp": "2026-01-01T00:00:20Z",
            "model": "claude-sonnet-4-6",
            "requestId": f"{session_id}-r2",
            "usage": {"input_tokens": 500, "output_tokens": 150},
            "name": "Write",
            "input": {"file_path": "src/app.py"},
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


@pytest.fixture
def isolated_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from cabal import session_reader

    root = tmp_path / "claude-projects"
    monkeypatch.setattr(session_reader, "_PROJECTS_DIR", root)
    monkeypatch.setattr(session_reader, "_WRITE_AUDIT_PATH", tmp_path / "write_audit.jsonl")
    return root


def test_Sessions_get_returns_paginated_v2_envelope_with_totals(
    app_factory, isolated_sessions: Path
) -> None:
    _write_session(isolated_sessions / "demo-project", "session-a")
    _write_session(isolated_sessions / "demo-project", "session-b", started="2026-01-02T00:00:00Z")
    _app, client = build_client(app_factory)

    response = client.get("/api/sessions?sort=date_desc", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    data = body["data"]
    assert TOTAL_KEYS <= set(data["totals"])
    assert data["totals"]["session_count"] == 2
    assert len(data["items"]) == 2
    for item in data["items"]:
        assert SESSION_KEYS <= set(item)
    assert data["items"][0]["session_id"] == "session-b"


def test_Sessions_get_honors_cursor_and_bounds_page_body(
    app_factory, isolated_sessions: Path
) -> None:
    project_dir = isolated_sessions / "huge-project"
    for index in range(105):
        _write_session(project_dir, f"session-{index:03d}", started=f"2026-01-01T00:{index % 60:02d}:00Z")
    _app, client = build_client(app_factory)

    first = client.get("/api/sessions?limit=25", headers=auth_headers()).json()["data"]
    second = client.get(f"/api/sessions?limit=25&cursor={first['next_cursor']}", headers=auth_headers()).json()[
        "data"
    ]

    assert len(first["items"]) == 25
    assert first["next_cursor"] == "25"
    assert len(second["items"]) == 25
    assert second["items"][0]["session_id"] != first["items"][0]["session_id"]


@pytest.mark.parametrize("tab", ("overview", "activity", "raw", "triggers"))
def test_SessionDetail_get_returns_lazy_tab_payload(
    app_factory, isolated_sessions: Path, tab: str
) -> None:
    _write_session(isolated_sessions / "demo-project", "session-a")
    _app, client = build_client(app_factory)

    response = client.get(f"/api/sessions/session-a?tab={tab}", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    assert body["data"]["session_id"] == "session-a"
    assert body["data"]["tab"] == tab
    assert "payload" in body["data"]


def test_SessionDelete_prepare_execute_removes_transcript_and_records_audit(
    app_factory, isolated_sessions: Path
) -> None:
    transcript = _write_session(isolated_sessions / "demo-project", "session-delete")
    _app, client = build_client(app_factory)

    prepared = client.post(
        "/api/actions/sessions.delete/prepare",
        json={"session_id": "session-delete"},
        headers=auth_headers(),
    )
    assert prepared.status_code == 200
    preview = prepared.json()["data"]["effect_preview"]
    assert preview["summary"]
    assert preview["removals"] == [str(transcript)]

    executed = client.post(
        "/api/actions/sessions.delete/execute",
        json={"ticket_id": prepared.json()["data"]["ticket_id"]},
        headers=auth_headers(),
    )

    assert executed.status_code == 200
    assert transcript.exists() is False
    audit = client.get("/api/audit", headers=auth_headers()).json()["data"]["entries"]
    assert any(entry["action_id"] == "sessions.delete" for entry in audit)


def test_Account_Doctor_Models_and_ClaudeInfo_return_v2_envelopes(app_factory, tmp_path: Path) -> None:
    _app, client = build_client(app_factory, project=tmp_path)

    account = client.get("/api/account", headers=auth_headers())
    doctor = client.get("/api/doctor", headers=auth_headers())
    models = client.get("/api/models", headers=auth_headers())
    info = client.get("/api/claude-info", headers=auth_headers())

    assert account.status_code == 200
    assert _envelope_shape_ok(account.json())
    assert {"authenticated", "identity", "credential_sources"} <= set(account.json()["data"])

    assert doctor.status_code == 200
    assert _envelope_shape_ok(doctor.json())
    assert {"findings", "counts", "from_cache"} <= set(doctor.json()["data"])

    assert models.status_code == 200
    assert _envelope_shape_ok(models.json())
    assert isinstance(models.json()["data"]["assignments"], list)
    for assignment in models.json()["data"]["assignments"]:
        assert MODEL_KEYS <= set(assignment)

    assert info.status_code == 200
    assert _envelope_shape_ok(info.json())
    assert {"documents", "runtime"} <= set(info.json()["data"])


@pytest.mark.parametrize("path", OBSERVABILITY_READ_ROUTES)
def test_ObservabilityRoute_missing_bearer_token_returns_401(app_factory, path: str) -> None:
    _app, client = build_client(app_factory)

    response = client.get(path)

    assert response.status_code == 401
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"
    assert body["data"] is None


@pytest.mark.parametrize("path", OBSERVABILITY_READ_ROUTES)
@pytest.mark.parametrize("method", ("POST", "PUT", "PATCH", "DELETE"))
def test_ObservabilityRoute_mutating_verb_returns_405(app_factory, path: str, method: str) -> None:
    _app, client = build_client(app_factory)

    response = client.request(method, path, headers=auth_headers())

    assert response.status_code == 405
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"
    assert body["data"] is None
