"""Contract tests for the Tools endpoints of specs/015-web-ui-overhaul/contracts/web-api.contract.md."""

from __future__ import annotations

import platform

import pytest

from cabal.tool_catalog import TOOL_CATEGORIES, TOOL_DEFINITIONS, InstallChannel

from .webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]

SCHEMA_VERSION = "cabal-web.v2"

# Real catalog keys (setup/src/cabal/tool_catalog.py) chosen for deterministic,
# platform-independent ToolStatus assertions rather than invented keys:
#   - "git": SourceStatus.VERIFIED, InstallChannel.PACKAGE, all platforms.
#   - "hermes-agent": SourceStatus.MANUAL_REQUIRED, InstallChannel.MANUAL, installer=None
#     -> always resolves to state "manual_required" regardless of host probe results.
#   - "vllm": platforms=("Linux",) -> always "unsupported" on a non-Linux host.
REAL_TOOL_KEY = "git"
MANUAL_REQUIRED_TOOL_KEY = "hermes-agent"
PLATFORM_RESTRICTED_TOOL_KEY = "vllm"
UNKNOWN_TOOL_KEY = "not-a-real-tool-zzz"

CATALOG_ITEM_KEYS = {
    "key",
    "label",
    "category",
    "description",
    "source_url",
    "source_state",
    "install_channel",
    "platforms",
    "badges",
    "safety_notes",
    "backup_policy",
    "versions_available",
}
TOOL_STATUS_KEYS = {"state", "current_version", "latest_version", "checked_at"}
DEFINITIVE_TOOL_STATES = {
    "installed",
    "update_available",
    "missing",
    "unsupported",
    "manual_required",
    "error",
}

TOOLS_READ_ROUTES = (
    "/api/tools",
    "/api/tools/status",
    f"/api/tools/{REAL_TOOL_KEY}/status",
    f"/api/tools/{REAL_TOOL_KEY}",
)


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


def test_ToolsCatalog_get_returns_v2_envelope_with_items_and_no_per_item_status(
    app_factory,
) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/tools", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    items = body["data"]["items"]
    assert len(items) == len(TOOL_DEFINITIONS)
    for item in items:
        assert CATALOG_ITEM_KEYS <= set(item)
        assert "status" not in item


def test_ToolsCatalog_get_item_shape_matches_real_catalog_entry_for_git(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/tools", headers=auth_headers())

    items = {item["key"]: item for item in response.json()["data"]["items"]}
    git_item = items[REAL_TOOL_KEY]
    assert git_item["label"] == "Git"
    assert git_item["category"] == "System & VCS"
    assert git_item["source_url"] == "https://git-scm.com/"
    assert git_item["install_channel"] == InstallChannel.PACKAGE.value
    assert git_item["source_state"] == "verified"
    assert isinstance(git_item["platforms"], list)
    assert isinstance(git_item["badges"], list)
    assert isinstance(git_item["versions_available"], list)


def test_ToolsCatalog_get_reports_source_state_manual_required_for_manual_tool(
    app_factory,
) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/tools", headers=auth_headers())

    items = {item["key"]: item for item in response.json()["data"]["items"]}
    manual_item = items[MANUAL_REQUIRED_TOOL_KEY]
    assert manual_item["source_state"] == "manual_required"
    assert manual_item["install_channel"] == InstallChannel.MANUAL.value


def test_ToolsCatalog_get_reports_category_counts_matching_tool_catalog_registry(
    app_factory,
) -> None:
    _app, client = build_client(app_factory)
    expected = {category.name: len(category.keys) for category in TOOL_CATEGORIES}

    response = client.get("/api/tools", headers=auth_headers())

    assert response.json()["data"]["category_counts"] == expected


def test_ToolsCatalog_get_reports_channel_counts_matching_install_channels(
    app_factory,
) -> None:
    _app, client = build_client(app_factory)
    expected: dict[str, int] = {}
    for tool in TOOL_DEFINITIONS:
        expected[tool.install_channel.value] = expected.get(tool.install_channel.value, 0) + 1

    response = client.get("/api/tools", headers=auth_headers())

    assert response.json()["data"]["channel_counts"] == expected


def test_ToolsStatus_bulk_get_every_item_state_is_definitive_never_loading(
    app_factory,
) -> None:
    """Assertion #5: zero cached probes still yields definitive states, never `loading`."""
    _app, client = build_client(app_factory)

    response = client.get("/api/tools/status", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    items = body["data"]["items"]
    assert items
    for item in items:
        assert TOOL_STATUS_KEYS <= set(item)
        assert item["state"] != "loading"
        assert item["state"] in DEFINITIVE_TOOL_STATES
        assert item["checked_at"]


def test_ToolsStatus_bulk_get_covers_every_catalog_key_exactly_once(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/tools/status", headers=auth_headers())

    keys = [item["key"] for item in response.json()["data"]["items"]]
    assert sorted(keys) == sorted(tool.key for tool in TOOL_DEFINITIONS)
    assert len(keys) == len(set(keys))


def test_ToolStatus_single_get_returns_definitive_state_and_checked_at_for_real_tool(
    app_factory,
) -> None:
    _app, client = build_client(app_factory)

    response = client.get(f"/api/tools/{REAL_TOOL_KEY}/status", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    data = body["data"]
    assert TOOL_STATUS_KEYS <= set(data)
    assert data["state"] != "loading"
    assert data["state"] in DEFINITIVE_TOOL_STATES
    assert data["checked_at"]


def test_ToolStatus_single_get_returns_manual_required_for_manual_required_source_tool(
    app_factory,
) -> None:
    _app, client = build_client(app_factory)

    response = client.get(f"/api/tools/{MANUAL_REQUIRED_TOOL_KEY}/status", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["data"]["state"] == "manual_required"


@pytest.mark.skipif(
    platform.system() == "Linux", reason="vllm is only unsupported off Linux hosts"
)
def test_ToolStatus_single_get_returns_unsupported_for_platform_restricted_tool(
    app_factory,
) -> None:
    _app, client = build_client(app_factory)

    response = client.get(f"/api/tools/{PLATFORM_RESTRICTED_TOOL_KEY}/status", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["data"]["state"] == "unsupported"


def test_ToolStatus_single_get_unknown_key_returns_404(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get(f"/api/tools/{UNKNOWN_TOOL_KEY}/status", headers=auth_headers())

    assert response.status_code == 404
    assert response.json()["schema_version"] == SCHEMA_VERSION


def test_ToolDetail_get_returns_full_shape_including_status_and_versions_available(
    app_factory,
) -> None:
    _app, client = build_client(app_factory)

    response = client.get(f"/api/tools/{REAL_TOOL_KEY}", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    data = body["data"]
    assert CATALOG_ITEM_KEYS <= set(data)
    assert isinstance(data["versions_available"], list)
    status = data["status"]
    assert TOOL_STATUS_KEYS <= set(status)
    assert status["state"] in DEFINITIVE_TOOL_STATES
    assert status["state"] != "loading"


def test_ToolDetail_get_unknown_key_returns_404(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get(f"/api/tools/{UNKNOWN_TOOL_KEY}", headers=auth_headers())

    assert response.status_code == 404
    assert response.json()["schema_version"] == SCHEMA_VERSION


@pytest.mark.parametrize("path", TOOLS_READ_ROUTES)
def test_ToolsRoute_missing_bearer_token_returns_401(app_factory, path: str) -> None:
    _app, client = build_client(app_factory)

    response = client.get(path)

    assert response.status_code == 401
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"
    assert body["data"] is None


@pytest.mark.parametrize("path", TOOLS_READ_ROUTES)
def test_ToolsRoute_wrong_bearer_token_returns_401(app_factory, path: str) -> None:
    _app, client = build_client(app_factory)

    response = client.get(path, headers=auth_headers("wrong-token"))

    assert response.status_code == 401


@pytest.mark.parametrize("path", TOOLS_READ_ROUTES)
@pytest.mark.parametrize("method", ("POST", "PUT", "PATCH", "DELETE"))
def test_ToolsRoute_mutating_verb_returns_405(app_factory, path: str, method: str) -> None:
    _app, client = build_client(app_factory)

    response = client.request(method, path, headers=auth_headers())

    assert response.status_code == 405
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"
    assert body["data"] is None
