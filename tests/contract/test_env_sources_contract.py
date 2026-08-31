# -*- coding: utf-8 -*-
"""Contract suite for GET /api/env/sources and POST /api/env/reveal (Constitution Gate 3).

Written and observed failing before the routes existed. The invariant IDs in the test names
are the ones tabulated in specs/020-env-variable-sources/contracts/.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from .webapi_fixtures import auth_headers, build_client

# Re-export the shared app_factory fixture (fixtures live in webapi_fixtures, not conftest).
from .webapi_fixtures import app_factory

__all__ = ["app_factory"]


@pytest.fixture
def local_only(monkeypatch):
    """Keep the local-source assertions off the network and off this machine's CLIs.

    Every test that is not specifically about a provider uses this: otherwise the suite's
    result depends on whether the machine happens to be signed in to Azure.
    """
    from cabal.webapi import envsources_service

    monkeypatch.setattr(envsources_service, "provider_specs", lambda _project: [])


def _seed_project(root: Path) -> Path:
    (root / ".env.local").write_text(
        "# local overrides\nDATABASE_URL=postgres://localhost/app\nAPI_KEY=abc123\n",
        encoding="utf-8",
    )
    (root / "appsettings.json").write_text(
        json.dumps({"Logging": {"LogLevel": {"Default": "Information"}}, "AllowedHosts": "*"}),
        encoding="utf-8",
    )
    nested = root / "services" / "billing"
    nested.mkdir(parents=True)
    (nested / "appsettings.json").write_text(json.dumps({"ConnectionStrings": {"Db": "x"}}), encoding="utf-8")
    junk = root / "node_modules" / "pkg"
    junk.mkdir(parents=True)
    (junk / ".env").write_text("SHOULD_NOT_APPEAR=1\n", encoding="utf-8")
    return root


def _sources(client, token_headers) -> dict:
    response = client.get("/api/env/sources", headers=token_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "environment"
    return body["data"]


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


# -- GET /api/env/sources ------------------------------------------------


def test_c1_no_object_in_the_listing_carries_a_value_key(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)

    data = _sources(client, auth_headers())

    assert '"value"' not in json.dumps(data)
    assert all("value" not in node for node in _walk(data))


def test_c2_every_degraded_source_carries_a_non_empty_hint(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)

    data = _sources(client, auth_headers())

    for source in data["sources"]:
        if source["state"] == "degraded":
            assert (source["hint"] or "").strip(), source


def test_c3_undetected_sources_are_absent_rather_than_not_linked(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)

    data = _sources(client, auth_headers())

    assert all(source["state"] != "not_linked" for source in data["sources"])


def test_c4_every_non_readable_entry_states_why(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)

    data = _sources(client, auth_headers())

    for source in data["sources"]:
        for container in source["containers"]:
            for entry in container["entries"]:
                if entry["retrievability"] != "readable":
                    assert (entry["retrievability_reason"] or "").strip(), entry


def test_c7_label_plus_qualifier_is_unique_across_every_container(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)

    data = _sources(client, auth_headers())

    keys = [
        (container["label"], container["qualifier"])
        for source in data["sources"]
        for container in source["containers"]
    ]
    assert len(keys) == len(set(keys)), keys


def test_one_container_per_discovered_config_file(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)

    data = _sources(client, auth_headers())

    labels = {
        container["label"]
        for source in data["sources"]
        if source["kind"] == "repo_file"
        for container in source["containers"]
    }
    assert {".env.local", "appsettings.json"} <= labels
    assert not any("SHOULD_NOT_APPEAR" in json.dumps(source) for source in data["sources"])


def test_listing_requires_a_bearer_token(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.get("/api/env/sources")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_listing_without_a_selected_project_is_refused(app_factory, local_only) -> None:
    _app, client = build_client(app_factory, project=None)

    response = client.get("/api/env/sources", headers=auth_headers())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_project_selected"


def test_c10_a_hanging_collector_is_degraded_and_does_not_hold_the_route(
    app_factory, tmp_path, monkeypatch
) -> None:
    from cabal.models.envsources import SourceKind
    from cabal.webapi import envsources_service

    _seed_project(tmp_path)
    release = threading.Event()

    def hangs(_project):
        release.wait(30)
        return []

    spec = envsources_service.CollectorSpec(
        id="test:hang", kind=SourceKind.GITHUB, label="Hanging provider", collect=hangs
    )
    monkeypatch.setattr(envsources_service, "provider_specs", lambda _project: [spec])
    monkeypatch.setattr(envsources_service, "TOTAL_TIMEOUT_S", 0.3)

    _app, client = build_client(app_factory, project=tmp_path)
    try:
        import time

        started = time.monotonic()
        data = _sources(client, auth_headers())
        elapsed = time.monotonic() - started
    finally:
        release.set()

    assert elapsed < 3.0
    hung = [source for source in data["sources"] if source["id"] == "test:hang"]
    assert hung and hung[0]["state"] == "degraded"
    assert "Hanging provider" in (hung[0]["hint"] or "")
    assert any(source["kind"] == "repo_file" for source in data["sources"])


# -- POST /api/env/reveal ------------------------------------------------


def _entry_ref(data: dict, name: str) -> dict:
    for source in data["sources"]:
        for container in source["containers"]:
            for entry in container["entries"]:
                if entry["name"] == name:
                    return {
                        "source_id": entry["source_id"],
                        "container_id": entry["container_id"],
                        "name": entry["name"],
                    }
    raise AssertionError(f"{name} not present in the listing")


def _reveal(client, body: dict):
    return client.post("/api/env/reveal", json=body, headers=auth_headers())


def test_r1_a_value_comes_back_only_when_the_status_is_revealed(
    app_factory, tmp_path, local_only
) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)
    reference = _entry_ref(_sources(client, auth_headers()), "DATABASE_URL")

    response = _reveal(client, reference)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "revealed"
    assert data["value"] == "postgres://localhost/app"
    assert data["reason"] is None


def test_r2_a_non_revealed_status_always_states_a_reason(app_factory, tmp_path, monkeypatch) -> None:
    from cabal.webapi import envsources_service

    _seed_project(tmp_path)
    monkeypatch.setattr(envsources_service, "provider_specs", lambda _project: [])
    _app, client = build_client(app_factory, project=tmp_path)

    response = _reveal(
        client,
        {"source_id": "github", "container_id": "github:repository:secrets", "name": "TOKEN"},
    )

    data = response.json()["data"]
    assert data["status"] == "unavailable"
    assert (data["reason"] or "").strip()
    assert data["value"] is None


def test_r3_a_never_entry_answers_without_contacting_the_provider(
    app_factory, tmp_path, monkeypatch
) -> None:
    from cabal import envsource_github_service

    _seed_project(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        envsource_github_service, "_api", lambda path: calls.append(path) or (1, "")
    )
    _app, client = build_client(app_factory, project=tmp_path)

    response = _reveal(
        client,
        {"source_id": "github", "container_id": "github:env:production:secrets", "name": "DB"},
    )

    assert response.json()["data"]["status"] == "unavailable"
    assert calls == []


def test_r4_every_call_writes_exactly_one_audit_record(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    app, client = build_client(app_factory, project=tmp_path)
    reference = _entry_ref(_sources(client, auth_headers()), "DATABASE_URL")
    before = len(app.state.audit.list())

    _reveal(client, reference)
    _reveal(
        client,
        {"source_id": "github", "container_id": "github:repository:secrets", "name": "TOKEN"},
    )

    records = app.state.audit.list()
    assert len(records) - before == 2
    assert all(record["action_id"] == "env.reveal" for record in records[before:])


def test_r5_no_audit_record_contains_the_revealed_value(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    app, client = build_client(app_factory, project=tmp_path)
    reference = _entry_ref(_sources(client, auth_headers()), "DATABASE_URL")

    _reveal(client, reference)

    assert "postgres://localhost/app" not in json.dumps(app.state.audit.list())


def test_r6_a_permission_refusal_is_a_denied_body_not_a_5xx(
    app_factory, tmp_path, monkeypatch
) -> None:
    from cabal import envsource_azure_service

    _seed_project(tmp_path)
    monkeypatch.setattr(
        envsource_azure_service, "_az", lambda args: (1, "ERROR: Forbidden by RBAC policy")
    )
    _app, client = build_client(app_factory, project=tmp_path)

    response = _reveal(
        client,
        {"source_id": "azure_keyvault", "container_id": "azure_keyvault:kv-prod", "name": "DbPw"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "denied"
    assert "Key Vault Secrets User" in data["reason"]


def test_r8_the_reveal_response_permits_no_caching(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)
    reference = _entry_ref(_sources(client, auth_headers()), "DATABASE_URL")

    response = _reveal(client, reference)

    assert "no-store" in response.headers.get("cache-control", "")


def test_r9_an_unknown_triple_is_a_404_not_a_partial_reveal(
    app_factory, tmp_path, local_only
) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)

    unknown_source = _reveal(
        client, {"source_id": "repo_file:nope", "container_id": "repo_file:nope", "name": "X"}
    )
    unknown_name = _reveal(
        client,
        {
            "source_id": "repo_file:.env.local",
            "container_id": "repo_file:.env.local",
            "name": "NOT_DECLARED",
        },
    )

    assert unknown_source.status_code == 404
    assert unknown_source.json()["error"]["code"] == "entry_not_found"
    assert unknown_name.status_code == 404


def test_r10_a_reveal_writes_nothing_to_disk(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)
    reference = _entry_ref(_sources(client, auth_headers()), "DATABASE_URL")
    secret = "postgres://localhost/app"
    source_file = tmp_path / ".env.local"
    before = source_file.read_bytes()

    assert _reveal(client, reference).json()["data"]["value"] == secret

    # The audit database is written on every reveal by design, so the assertion is not
    # "nothing changed" but the one FR-015 actually makes: the value reaches no file. The
    # config file it came from is the only place on disk it may appear, unchanged.
    written = [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path != source_file and secret.encode() in path.read_bytes()
    ]
    assert written == []
    assert source_file.read_bytes() == before


def test_reveal_rejects_a_batch_request(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)

    response = _reveal(
        client,
        {
            "source_id": "repo_file:.env.local",
            "container_id": "repo_file:.env.local",
            "name": ["DATABASE_URL", "API_KEY"],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "params_invalid"


def test_reveal_requires_a_bearer_token(app_factory, tmp_path, local_only) -> None:
    _seed_project(tmp_path)
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.post("/api/env/reveal", json={"source_id": "a", "container_id": "b", "name": "c"})

    assert response.status_code == 401


def test_reveal_without_a_selected_project_is_refused(app_factory, local_only) -> None:
    _app, client = build_client(app_factory, project=None)

    response = _reveal(client, {"source_id": "a", "container_id": "b", "name": "c"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_project_selected"
