"""Contract tests for the SnapshotEnvelope/auth base of specs/015-web-ui-overhaul/contracts/web-api.contract.md."""

from __future__ import annotations

import json

import pytest

from .webapi_fixtures import FAKE_SECRET, app_factory, auth_headers, build_client

__all__ = ["app_factory"]

SCHEMA_VERSION = "cabal-web.v2"
FOUNDATIONAL_READ_ROUTES = ("/api/health", "/api/diagnostics", "/api/jobs")


def test_health_route_returns_v2_envelope_shape(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/health", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] in {"ok", "degraded", "error"}
    assert isinstance(body["captured_at"], str) and body["captured_at"]
    assert isinstance(body["source"], str) and body["source"]
    assert isinstance(body["stale"], bool)
    assert "precondition_digest" in body
    assert "data" in body
    assert "error" in body


def test_health_data_contains_module_health_rows(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/health", headers=auth_headers())

    assert response.status_code == 200
    modules = response.json()["data"]["modules"]
    assert len(modules) >= 1
    for row in modules:
        assert {"module", "state", "detail", "last_success_at"} <= set(row)
        assert row["state"] in {"ok", "loading", "degraded", "failed", "unavailable"}


@pytest.mark.parametrize("path", FOUNDATIONAL_READ_ROUTES)
def test_missing_bearer_token_returns_401(app_factory, path: str) -> None:
    _app, client = build_client(app_factory)

    response = client.get(path)

    assert response.status_code == 401
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"
    assert body["data"] is None


@pytest.mark.parametrize("path", FOUNDATIONAL_READ_ROUTES)
def test_wrong_bearer_token_returns_401(app_factory, path: str) -> None:
    _app, client = build_client(app_factory)

    response = client.get(path, headers=auth_headers("wrong-token"))

    assert response.status_code == 401
    assert response.json()["status"] == "error"


@pytest.mark.parametrize("path", FOUNDATIONAL_READ_ROUTES)
@pytest.mark.parametrize("method", ("POST", "PUT", "PATCH", "DELETE"))
def test_mutating_verbs_on_read_routes_return_405(app_factory, path: str, method: str) -> None:
    _app, client = build_client(app_factory)

    response = client.request(method, path, headers=auth_headers())

    assert response.status_code == 405
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"
    assert body["data"] is None


def test_unknown_route_returns_404_envelope(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/this-route-does-not-exist", headers=auth_headers())

    assert response.status_code == 404
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"


def test_seeded_secret_in_diagnostic_is_never_echoed_in_any_response_body(app_factory) -> None:
    app, client = build_client(app_factory)
    app.state.diagnostics.record(
        severity="error",
        module="tools",
        message=f"probe failed using {FAKE_SECRET}",
    )

    for path in FOUNDATIONAL_READ_ROUTES:
        response = client.get(path, headers=auth_headers())
        assert FAKE_SECRET not in response.text
        assert FAKE_SECRET not in json.dumps(response.json())


def test_diagnostics_route_lists_the_redacted_seeded_event(app_factory) -> None:
    app, client = build_client(app_factory)
    app.state.diagnostics.record(
        severity="warning",
        module="mcp",
        message=f"handshake leaked {FAKE_SECRET}",
    )

    response = client.get("/api/diagnostics", headers=auth_headers())

    assert response.status_code == 200
    events = response.json()["data"]["events"]
    assert any("handshake leaked" in event["message"] for event in events)
    assert all(FAKE_SECRET not in event["message"] for event in events)
