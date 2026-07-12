"""Contract tests for specs/015-web-ui-overhaul/contracts/action-safety.contract.md."""

from __future__ import annotations

import json

from .webapi_fixtures import (
    FAKE_SECRET,
    app_factory,
    auth_headers,
    build_client,
    register_fixture_actions,
)

__all__ = ["app_factory"]


def _prepare(client, action_id: str, params: dict | None = None):
    return client.post(f"/api/actions/{action_id}/prepare", json=params or {}, headers=auth_headers())


def _execute(client, action_id: str, ticket_id: str):
    return client.post(
        f"/api/actions/{action_id}/execute",
        json={"ticket_id": ticket_id},
        headers=auth_headers(),
    )


def test_execute_without_prepare_returns_404_or_409(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)

    response = _execute(client, "test.echo", "never-prepared-ticket-id")

    assert response.status_code in {404, 409}


def test_prepare_then_execute_round_trip_writes_exactly_one_audit_entry(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)

    prepared = _prepare(client, "test.echo", {"note": "hello"})
    assert prepared.status_code == 200
    ticket = prepared.json()["data"]
    assert ticket["action_id"] == "test.echo"
    assert ticket["effect_preview"]["summary"]
    assert "precondition_digest" in ticket

    executed = _execute(client, "test.echo", ticket["ticket_id"])
    assert executed.status_code == 200
    assert executed.json()["data"]["echoed"] == "hello"

    audit = client.get("/api/audit", headers=auth_headers())
    entries = audit.json()["data"]["entries"]
    matching = [e for e in entries if e["ticket_id"] == ticket["ticket_id"]]
    assert len(matching) == 1
    assert matching[0]["outcome"] == "succeeded"


def test_digest_drift_between_prepare_and_execute_returns_409_with_no_side_effect(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)

    prepared = _prepare(client, "test.echo", {"note": "before"})
    ticket = prepared.json()["data"]

    app.state.test_source_value = "mutated"

    executed = _execute(client, "test.echo", ticket["ticket_id"])
    assert executed.status_code == 409
    assert executed.json()["error"]["code"] == "state_changed"
    assert executed.json()["data"] is None

    reprepared = _prepare(client, "test.echo", {"note": "before"})
    assert reprepared.json()["data"]["ticket_id"] != ticket["ticket_id"]

    second_execute = _execute(client, "test.echo", ticket["ticket_id"])
    assert second_execute.status_code in {404, 409, 410}


def test_ticket_reuse_returns_409_and_expired_ticket_returns_410(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)

    prepared = _prepare(client, "test.echo", {"note": "once"})
    ticket = prepared.json()["data"]

    first = _execute(client, "test.echo", ticket["ticket_id"])
    assert first.status_code == 200

    reused = _execute(client, "test.echo", ticket["ticket_id"])
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "ticket_consumed"

    expired_ticket = _prepare(client, "test.echo", {"note": "expires"}).json()["data"]
    app.state.actions.force_expire_ticket_for_test(expired_ticket["ticket_id"])

    expired_response = _execute(client, "test.echo", expired_ticket["ticket_id"])
    assert expired_response.status_code == 410
    assert expired_response.json()["error"]["code"] == "ticket_expired"


def test_registry_self_check_destructive_descriptor_populates_removals_and_backup(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)

    for action_id in app.state.actions.ids():
        descriptor = app.state.actions.get(action_id)
        if not descriptor.destructive:
            continue
        response = _prepare(client, action_id, {})
        assert response.status_code == 200, action_id
        preview = response.json()["data"]["effect_preview"]
        assert preview["removals"], f"{action_id} destructive but removals empty"
        assert preview["backup"], f"{action_id} destructive but backup empty"


def test_prepare_previews_are_non_empty_and_redact_seeded_secret_in_params(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)

    for action_id in app.state.actions.ids():
        descriptor = app.state.actions.get(action_id)
        if action_id != "test.echo" and descriptor.params_schema.get("required"):
            # Real production actions (e.g. project.select) may legitimately require
            # caller-supplied params that a blank {} can't satisfy; their own
            # non-empty-summary + redaction guarantee is covered by that action's
            # dedicated contract test instead of this generic blank-params sweep.
            continue
        response = _prepare(client, action_id, {"note": FAKE_SECRET} if action_id == "test.echo" else {})
        assert response.status_code == 200, action_id
        preview = response.json()["data"]["effect_preview"]
        assert preview["summary"]
        assert FAKE_SECRET not in json.dumps(preview)


def test_get_sweep_across_read_routes_performs_zero_writes(app_factory) -> None:
    app, client = build_client(app_factory)
    register_fixture_actions(app)
    app.state.write_guard.reset()

    read_paths = [
        route.path
        for route in app.routes
        if getattr(route, "methods", None)
        and "GET" in route.methods
        and route.path.startswith("/api/")
        and "{" not in route.path
    ]
    assert read_paths, "expected at least one mounted GET /api/* route"

    for path in read_paths:
        response = client.get(path, headers=auth_headers())
        # A bare route missing a required selector query param (e.g.
        # /api/dashboard without ?section=) legitimately 422s; that's still a
        # zero-write response, which is the invariant this sweep guards.
        assert response.status_code in {200, 404, 422}

    assert app.state.write_guard.count == 0
