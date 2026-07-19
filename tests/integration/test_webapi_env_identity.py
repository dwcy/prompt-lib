"""Security-fix, environment-apply, and git-policy validation integration tests."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from contract.webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]


def _prepare(client, action_id: str, params: dict):
    return client.post(
        f"/api/actions/{action_id}/prepare", json=params, headers=auth_headers()
    )


def _execute(client, action_id: str, ticket_id: str):
    return client.post(
        f"/api/actions/{action_id}/execute",
        json={"ticket_id": ticket_id},
        headers=auth_headers(),
    )


def test_fix_preview_command_matches_execution_and_env_apply_round_trips(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.package_security.models import Finding, ScanOutcome
    from cabal.webapi.routers import environment as environment_router
    from cabal.webapi.routers import security_scan as security_router

    finding = Finding(
        ecosystem="python",
        package="fixture-package",
        kind="outdated",
        severity="warning",
        current_version="1.0",
        target_version="1.1",
        fix_command="uv add fixture-package==1.1",
    )
    outcomes = (ScanOutcome(ecosystem="python", findings=(finding,)),)
    monkeypatch.setattr(security_router.package_security, "load_cached", lambda _project: outcomes)
    executed_commands: list[str] = []

    def apply_fix(selected, _project):
        executed_commands.append(str(selected.fix_command))
        return True, "fixture fixed"

    monkeypatch.setattr(security_router.package_security, "apply_fix", apply_fix)
    monkeypatch.setattr(security_router.package_security, "clear_cache", lambda _project: None)
    env_file = tmp_path / "setup.env.example.json"
    env_file.write_text(json.dumps({"PROJECTS_PATH": ""}), encoding="utf-8")
    monkeypatch.setattr(environment_router, "ENV_FILE", env_file)
    monkeypatch.setattr(environment_router.platform, "system", lambda: "Windows")
    monkeypatch.delenv("PROJECTS_PATH", raising=False)

    def fake_run(argv, **_kwargs):
        if argv[:2] == ["setx", "PROJECTS_PATH"]:
            os.environ["PROJECTS_PATH"] = argv[2]
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(environment_router.subprocess, "run", fake_run)
    _app, client = build_client(app_factory, project=tmp_path)

    prepared_fix = _prepare(
        client, "security.apply_fix", {"finding_key": finding.key}
    )
    assert prepared_fix.status_code == 200
    fix_ticket = prepared_fix.json()["data"]
    assert fix_ticket["effect_preview"]["commands"] == [finding.fix_command]
    started = _execute(client, "security.apply_fix", fix_ticket["ticket_id"])
    assert started.status_code == 202
    job_id = started.json()["data"]["job_id"]
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}", headers=auth_headers()).json()["data"]
        if job["state"] in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(0.01)
    assert job["state"] == "succeeded"
    assert executed_commands == [fix_ticket["effect_preview"]["commands"][0]]

    env_value = str(tmp_path / "projects")
    prepared_env = _prepare(client, "env.apply", {"values": {"PROJECTS_PATH": env_value}})
    assert prepared_env.status_code == 200
    applied_env = _execute(client, "env.apply", prepared_env.json()["data"]["ticket_id"])
    assert applied_env.status_code == 200
    current = client.get("/api/env", headers=auth_headers()).json()["data"]
    row = next(item for item in current["entries"] if item["name"] == "PROJECTS_PATH")
    assert row["value_redacted"] == env_value
    assert row["source"] == "system"


@pytest.mark.parametrize(
    "mutation",
    [
        {"allowed_types": "feat"},
        {"refuse_on_branches": ["main", 7]},
        {"tags": {"agent_may_tag": "yes", "auto_push": False}},
    ],
)
def test_policy_prepare_rejects_bad_field_types(app_factory, mutation: dict) -> None:
    _app, client = build_client(app_factory)
    policy = {
        "agent_name": "Fixture Agent",
        "agent_email": "fixture@example.test",
        "allowed_types": ["feat", "fix"],
        "refuse_on_branches": ["main", "master"],
        "tags": {"agent_may_tag": False, "auto_push": False},
    }
    policy.update(mutation)

    response = _prepare(client, "git.policy.set", policy)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "params_invalid"
