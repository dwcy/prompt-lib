"""Contract tests for the read-only Cabal web data API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal.models.dashboard import AvailabilityState
from cabal.web import SCHEMA_VERSION
from cabal.web import api as api_module
from cabal.web import serializers
from cabal.web.api import WebApi


ENDPOINTS = (
    "/api/health",
    "/api/diagnostics",
    "/api/tools",
    "/api/knowledge",
    "/api/project-health",
    "/api/overview",
)

TOOL_FIELDS = {
    "key",
    "label",
    "category",
    "description",
    "source_url",
    "source_label",
    "source_status",
    "install_channel",
    "platforms",
    "supports_current_platform",
    "status",
    "status_detail",
    "version_provider",
    "backup_policy",
    "badges",
    "safety_notes",
}


def _token() -> str:
    return "github_pat_" + ("A" * 30)


def _section(title: str, state: str = AvailabilityState.OK.value) -> dict:
    return {
        "state": state,
        "title": title,
        "summary": f"{title} ready",
        "facts": [{"label": "branch", "value": "main"}],
        "links": [],
        "hint": None,
    }


def _project_health(_root: Path) -> dict:
    return {
        "project_path": "repo",
        "captured_at": "2026-06-29T08:00:00Z",
        "git": _section("Git"),
        "github": _section("GitHub", AvailabilityState.NOT_AUTHED.value),
        "supabase": _section("Supabase", AvailabilityState.TOKEN_MISSING.value),
        "vercel": _section("Vercel", AvailabilityState.NOT_LINKED.value),
        "diagnostics": [],
    }


@pytest.fixture
def deterministic_sources(monkeypatch):
    monkeypatch.setattr(serializers, "_probe_key", lambda _key: "1.0.0")
    monkeypatch.setattr(serializers, "_tool_unavailable_reason", lambda _key: None)
    monkeypatch.setattr(serializers, "serialize_project_health", _project_health)
    monkeypatch.setattr(api_module, "serialize_project_health", _project_health)


@pytest.mark.parametrize("path", ENDPOINTS)
def test_every_endpoint_returns_versioned_envelope(path, tmp_path, deterministic_sources) -> None:
    api = WebApi(tmp_path)

    status, body = api.handle(path)

    assert status == 200
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["captured_at"].endswith("Z")
    assert body["status"] in {"ok", "partial", "stale", "error"}
    assert body["source"]
    assert "data" in body
    assert "error" in body


@pytest.mark.parametrize("method", ("POST", "PUT", "PATCH", "DELETE"))
def test_mutating_methods_return_405(method, tmp_path) -> None:
    status, body = WebApi(tmp_path).handle("/api/tools", method)

    assert status == 405
    assert body["status"] == "error"
    assert body["error"]["retryable"] is False


def test_unknown_route_returns_redacted_404_envelope(tmp_path) -> None:
    token = _token()

    status, body = WebApi(tmp_path).handle(f"/api/unknown?token={token}")

    assert status == 404
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"
    assert token not in json.dumps(body)


def test_tools_endpoint_includes_required_tool_metadata(tmp_path, deterministic_sources) -> None:
    status, body = WebApi(tmp_path).handle("/api/tools")

    assert status == 200
    data = body["data"]
    assert data["categories"]
    assert data["items"]
    assert TOOL_FIELDS <= set(data["items"][0])
    assert data["status_counts"]
    assert data["source_status_counts"]
    assert data["install_channel_counts"]


def test_missing_knowledge_graph_is_successful_empty_state(tmp_path, deterministic_sources) -> None:
    status, body = WebApi(tmp_path).handle("/api/knowledge")

    assert status == 200
    assert body["status"] == "ok"
    assert body["data"]["available"] is False
    assert body["data"]["nodes"] == []
    assert body["data"]["edges"] == []
    assert body["data"]["diagnostics"][0]["severity"] == "info"


def test_project_health_endpoint_includes_required_sections(tmp_path, deterministic_sources) -> None:
    status, body = WebApi(tmp_path).handle("/api/project-health")

    assert status == 200
    data = body["data"]
    for key in ("git", "github", "supabase", "vercel"):
        assert {"state", "title", "summary", "facts", "links", "hint"} <= set(data[key])


def test_overview_endpoint_reports_partial_section_failures(
    tmp_path, monkeypatch, deterministic_sources
) -> None:
    def broken_project_health(_root: Path) -> dict:
        raise RuntimeError("TOKEN=" + _token())

    monkeypatch.setattr(serializers, "serialize_project_health", broken_project_health)

    status, body = WebApi(tmp_path).handle("/api/overview")

    assert status == 200
    assert body["status"] == "partial"
    assert any(section["state"] == "error" for section in body["data"]["sections"])
    assert _token() not in json.dumps(body)


def test_api_responses_do_not_contain_raw_token_fixture(tmp_path, deterministic_sources) -> None:
    token = _token()
    api = WebApi(tmp_path)
    api._diagnostics.append(serializers.diagnostic_event("health", f"failed with {token}"))

    for path in ENDPOINTS:
        _status, body = api.handle(path)
        assert token not in json.dumps(body)
