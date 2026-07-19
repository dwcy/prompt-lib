"""Contract tests for the config-lifecycle endpoints (US3) of
specs/015-web-ui-overhaul/contracts/web-api.contract.md:
/api/config/{tree,diff,extras,backups}, /api/settings, /api/local-config,
/api/codex/conversion, plus the digest-stability assertion (#7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cabal._paths import GLOBAL_DIR

from .webapi_fixtures import auth_headers, build_client

# Re-export the shared app_factory fixture (fixtures live in webapi_fixtures, not conftest).
from .webapi_fixtures import app_factory

__all__ = ["app_factory"]

SCHEMA_VERSION = "cabal-web.v2"

CONFIG_READ_ROUTES = (
    "/api/config/tree?target=claude",
    "/api/config/tree?target=codex",
    "/api/config/extras?target=claude",
    "/api/config/backups?kind=cleanup",
    "/api/config/backups?kind=settings",
    "/api/settings",
    "/api/local-config",
    "/api/codex/conversion",
)

TREE_FILE_KEYS = {"rel_path", "state", "diff_available"}
TREE_COMPONENT_KEYS = {"key", "label", "group", "files"}
DRIFT_KEYS = {"target", "changed_count", "new_count", "unchanged_count", "extras_count", "computed_at", "digest"}
FILE_STATES = {"new", "changed", "unchanged"}
SETTING_KEYS = {"key", "label", "description", "source", "value_state", "target_file"}
SETTING_SOURCES = {"global", "local_override", "unset"}
LOCAL_ACTION_KEYS = {"key", "label", "applicable", "applied_state", "preview_items"}
PREVIEW_ITEM_KEYS = {"rel_path", "state", "selected"}
PREVIEW_STATES = {"new", "changed", "skip"}
CONVERSION_ROW_KEYS = {"asset", "state", "kind", "source_path", "output_path", "reason"}
CONVERSION_STATES = {"converted", "not-converted", "codex-only", "stale", "unsupported"}
EXTRA_KEYS = {"rel_path", "classification", "reason"}
BACKUP_KEYS = {"id", "kind", "created_at", "files_count", "restorable"}


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


# --- /api/config/tree -------------------------------------------------------


@pytest.mark.parametrize("target", ("claude", "codex"))
def test_ConfigTree_get_returns_v2_envelope_with_components_files_and_drift(app_factory, target: str) -> None:
    _app, client = build_client(app_factory)

    response = client.get(f"/api/config/tree?target={target}", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    data = body["data"]
    assert data["target"] == target
    assert isinstance(data["components"], list)
    for component in data["components"]:
        assert TREE_COMPONENT_KEYS <= set(component)
        for file_entry in component["files"]:
            assert TREE_FILE_KEYS <= set(file_entry)
            assert file_entry["state"] in FILE_STATES
            assert isinstance(file_entry["diff_available"], bool)
    assert DRIFT_KEYS <= set(data["drift"])
    assert data["drift"]["digest"].startswith("sha256:")


def test_ConfigTree_get_precondition_digest_matches_drift_digest(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/config/tree?target=claude", headers=auth_headers())

    body = response.json()
    assert body["precondition_digest"] == body["data"]["drift"]["digest"]


def test_ConfigTree_get_missing_target_returns_422(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/config/tree", headers=auth_headers())

    assert response.status_code == 422


def test_ConfigTree_get_unknown_target_returns_422(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/config/tree?target=bogus", headers=auth_headers())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "params_invalid"


# Assertion #7: digest stable for identical source state, changes when source changes.
def test_ConfigTree_digest_is_stable_across_identical_reads(app_factory) -> None:
    _app, client = build_client(app_factory)

    first = client.get("/api/config/tree?target=claude", headers=auth_headers()).json()
    second = client.get("/api/config/tree?target=claude", headers=auth_headers()).json()

    assert first["data"]["drift"]["digest"] == second["data"]["drift"]["digest"]


def test_ConfigTree_digest_changes_when_deployed_state_changes(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal import components

    isolated_target = tmp_path / "isolated-claude"
    isolated_target.mkdir()
    monkeypatch.setattr(components, "TARGET", isolated_target)
    _app, client = build_client(app_factory)

    empty_digest = client.get("/api/config/tree?target=claude", headers=auth_headers()).json()[
        "data"
    ]["drift"]["digest"]

    # Deploy one plain-text component file so its state flips NEW -> UNCHANGED.
    source_claude_md = GLOBAL_DIR / "CLAUDE.md"
    (isolated_target / "CLAUDE.md").write_text(
        source_claude_md.read_text(encoding="utf-8"), encoding="utf-8"
    )
    changed_digest = client.get("/api/config/tree?target=claude", headers=auth_headers()).json()[
        "data"
    ]["drift"]["digest"]

    assert empty_digest != changed_digest


# --- /api/config/diff -------------------------------------------------------


def test_ConfigDiff_get_returns_v2_envelope_with_diff_text_for_a_tree_file(app_factory) -> None:
    _app, client = build_client(app_factory)
    tree = client.get("/api/config/tree?target=claude", headers=auth_headers()).json()["data"]
    target_path = None
    for component in tree["components"]:
        for file_entry in component["files"]:
            if file_entry["diff_available"]:
                target_path = file_entry["rel_path"]
                break
        if target_path is not None:
            break
    if target_path is None:
        pytest.skip("no changed/new deployable file on this machine to diff")

    response = client.get(
        f"/api/config/diff?target=claude&path={target_path}", headers=auth_headers()
    )

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    assert body["data"]["rel_path"] == target_path
    assert isinstance(body["data"]["diff_text"], str)


def test_ConfigDiff_get_missing_path_param_returns_422(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/config/diff?target=claude", headers=auth_headers())

    assert response.status_code == 422


def test_ConfigDiff_get_unknown_path_returns_404(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get(
        "/api/config/diff?target=claude&path=not/a/real/file.zzz", headers=auth_headers()
    )

    assert response.status_code == 404


# --- /api/config/extras -----------------------------------------------------


def test_ConfigExtras_get_returns_v2_envelope_with_grouped_extras(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/config/extras?target=claude", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    data = body["data"]
    assert data["target"] == "claude"
    assert isinstance(data["groups"], list)
    for group in data["groups"]:
        assert {"component", "label", "extras"} <= set(group)
        for extra in group["extras"]:
            assert EXTRA_KEYS <= set(extra)
            assert extra["classification"] in {"stale", "unknown"}


# --- /api/config/backups ----------------------------------------------------


@pytest.mark.parametrize("kind", ("cleanup", "settings"))
def test_ConfigBackups_get_returns_v2_envelope_with_backup_list(app_factory, kind: str) -> None:
    _app, client = build_client(app_factory)

    response = client.get(f"/api/config/backups?kind={kind}", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    data = body["data"]
    assert data["kind"] == kind
    assert isinstance(data["backups"], list)
    for backup in data["backups"]:
        assert BACKUP_KEYS <= set(backup)
        assert backup["kind"] == kind


def test_ConfigBackups_get_unknown_kind_returns_422(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/config/backups?kind=bogus", headers=auth_headers())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "params_invalid"


# --- /api/settings ----------------------------------------------------------


def test_Settings_get_returns_v2_envelope_with_cataloged_entries(app_factory, tmp_path: Path) -> None:
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.get("/api/settings", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    entries = body["data"]["entries"]
    assert entries
    for entry in entries:
        assert SETTING_KEYS <= set(entry)
        assert entry["source"] in SETTING_SOURCES
        assert isinstance(entry["value_state"], bool)


# --- /api/local-config ------------------------------------------------------


def test_LocalConfig_get_returns_v2_envelope_with_actions_and_previews(app_factory, tmp_path: Path) -> None:
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.get("/api/local-config", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    data = body["data"]
    assert isinstance(data["actions"], list)
    for action in data["actions"]:
        assert LOCAL_ACTION_KEYS <= set(action)
        for item in action["preview_items"]:
            assert PREVIEW_ITEM_KEYS <= set(item)
            assert item["state"] in PREVIEW_STATES
            assert isinstance(item["selected"], bool)


# --- /api/codex/conversion --------------------------------------------------


def test_CodexConversion_get_returns_v2_envelope_with_conversion_rows(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/codex/conversion", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert _envelope_shape_ok(body)
    rows = body["data"]["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert CONVERSION_ROW_KEYS <= set(row)
        assert row["state"] in CONVERSION_STATES


# --- auth / method guards (shared across all config read routes) -------------


@pytest.mark.parametrize("path", CONFIG_READ_ROUTES)
def test_ConfigRoute_missing_bearer_token_returns_401(app_factory, path: str) -> None:
    _app, client = build_client(app_factory)

    response = client.get(path)

    assert response.status_code == 401
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"
    assert body["data"] is None


@pytest.mark.parametrize("path", CONFIG_READ_ROUTES)
def test_ConfigRoute_wrong_bearer_token_returns_401(app_factory, path: str) -> None:
    _app, client = build_client(app_factory)

    response = client.get(path, headers=auth_headers("wrong-token"))

    assert response.status_code == 401


@pytest.mark.parametrize("path", CONFIG_READ_ROUTES)
@pytest.mark.parametrize("method", ("POST", "PUT", "PATCH", "DELETE"))
def test_ConfigRoute_mutating_verb_returns_405(app_factory, path: str, method: str) -> None:
    _app, client = build_client(app_factory)

    response = client.request(method, path, headers=auth_headers())

    assert response.status_code == 405
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["status"] == "error"
    assert body["data"] is None


@pytest.mark.parametrize(
    ("action_id", "params"),
    (
        ("config.cleanup", {"paths": ["../outside.txt"]}),
        ("config.restore_cleanup", {"backup_id": "../outside"}),
        ("config.restore_settings", {"backup_id": "../settings.json.bak.evil"}),
    ),
)
def test_ConfigActions_prepare_rejects_paths_outside_managed_sources(
    app_factory, action_id: str, params: dict
) -> None:
    _app, client = build_client(app_factory)

    response = client.post(
        f"/api/actions/{action_id}/prepare",
        json=params,
        headers=auth_headers(),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "params_invalid"
