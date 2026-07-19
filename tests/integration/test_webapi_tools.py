"""Integration test: tools.install end-to-end (prepare, execute, job, status, audit)."""

from __future__ import annotations

import time
from typing import Callable

import pytest

from contract.webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]

# Real catalog key (setup/src/cabal/tool_catalog.py) with a working installer mapping
# (setup/src/cabal/tools.py INSTALLER_FUNCTIONS) and no backup_policy, so the runner
# closure in actions_catalog/tools.py skips backup_before_install entirely and the
# fake installer is the only seam this test needs to patch.
TEST_TOOL_KEY = "headroom"
TEST_TOOL_LABEL = "Headroom"
FAKE_INSTALLED_VERSION = "9.9.9"
TERMINAL_JOB_STATES = {"succeeded", "failed", "cancelled"}


def _wait_until(predicate: Callable[[], object], *, timeout: float = 5.0, interval: float = 0.02) -> object:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    pytest.fail("condition not met within timeout")


def _patch_installer(monkeypatch: pytest.MonkeyPatch, *, succeed: bool, message: str) -> dict[str, bool]:
    """Fake only the installer callable + live probe for TEST_TOOL_KEY; delegate every
    other key to the real registry/probe so the rest of the catalog behaves normally.
    """
    from cabal.tools import _installer_for as real_installer_for
    from cabal.tools import _probe_key as real_probe_key

    installed_state = {"done": False}

    def fake_installer() -> tuple[bool, str]:
        installed_state["done"] = succeed
        return succeed, message

    def fake_installer_for(key: str):
        if key == TEST_TOOL_KEY:
            return TEST_TOOL_LABEL, fake_installer
        return real_installer_for(key)

    def fake_probe_key(key: str) -> object:
        if key == TEST_TOOL_KEY:
            return FAKE_INSTALLED_VERSION if installed_state["done"] else None
        return real_probe_key(key)

    monkeypatch.setattr("cabal.webapi.actions_catalog.tools._installer_for", fake_installer_for)
    monkeypatch.setattr("cabal.webapi.tools_service._probe_key", fake_probe_key)
    return installed_state


def _prepare_install(client) -> dict:
    response = client.post(
        "/api/actions/tools.install/prepare",
        json={"key": TEST_TOOL_KEY},
        headers=auth_headers(),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _execute_install(client, ticket_id: str) -> dict:
    response = client.post(
        "/api/actions/tools.install/execute",
        json={"ticket_id": ticket_id},
        headers=auth_headers(),
    )
    assert response.status_code == 202, response.text
    return response.json()["data"]


def _wait_for_terminal_job(client, job_id: str) -> dict:
    def _fetch() -> dict | None:
        body = client.get(f"/api/jobs/{job_id}", headers=auth_headers()).json()["data"]
        return body if body["state"] in TERMINAL_JOB_STATES else None

    return _wait_until(_fetch)


def _wait_for_audit_entry(client, ticket_id: str) -> dict:
    def _fetch() -> dict | None:
        entries = client.get("/api/audit", headers=auth_headers()).json()["data"]["entries"]
        matching = [entry for entry in entries if entry["ticket_id"] == ticket_id]
        return matching[0] if matching else None

    return _wait_until(_fetch)


def test_ToolsInstall_end_to_end_flow_succeeds_and_status_and_audit_reflect_it(
    app_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _app, client = build_client(app_factory)
    installed_state = _patch_installer(monkeypatch, succeed=True, message="fake install output")

    ticket = _prepare_install(client)
    assert ticket["effect_preview"]["summary"] == f"Install {TEST_TOOL_LABEL}"

    outcome = _execute_install(client, ticket["ticket_id"])
    job_id = outcome["job_id"]

    job_record = _wait_for_terminal_job(client, job_id)
    assert job_record["state"] == "succeeded"
    assert installed_state["done"] is True

    status = client.get(f"/api/tools/{TEST_TOOL_KEY}/status", headers=auth_headers())
    assert status.status_code == 200
    status_data = status.json()["data"]
    assert status_data["state"] == "installed"
    assert status_data["current_version"] == FAKE_INSTALLED_VERSION

    audit_entry = _wait_for_audit_entry(client, ticket["ticket_id"])
    assert audit_entry["action_id"] == "tools.install"
    assert audit_entry["job_id"] == job_id
    assert audit_entry["outcome"] == "succeeded"

    all_entries = client.get("/api/audit", headers=auth_headers()).json()["data"]["entries"]
    matching = [entry for entry in all_entries if entry["action_id"] == "tools.install"]
    assert len(matching) == 1


def test_ToolsInstall_end_to_end_flow_fails_and_status_stays_missing_with_failed_audit(
    app_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _app, client = build_client(app_factory)
    installed_state = _patch_installer(monkeypatch, succeed=False, message="fake failure reason")

    ticket = _prepare_install(client)
    outcome = _execute_install(client, ticket["ticket_id"])
    job_id = outcome["job_id"]

    job_record = _wait_for_terminal_job(client, job_id)
    assert job_record["state"] == "failed"
    assert job_record["exit_detail"] == "fake failure reason"
    assert installed_state["done"] is False

    status = client.get(f"/api/tools/{TEST_TOOL_KEY}/status", headers=auth_headers())
    assert status.json()["data"]["state"] == "missing"

    audit_entry = _wait_for_audit_entry(client, ticket["ticket_id"])
    assert audit_entry["action_id"] == "tools.install"
    assert audit_entry["job_id"] == job_id
    assert audit_entry["outcome"] == "failed"
