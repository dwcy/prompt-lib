from __future__ import annotations

import json
from pathlib import Path

import pytest

from contract.webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]


def _write_task(root: Path) -> Path:
    path = root / "claude-code-sessions" / "workspace" / "session" / "scheduled-tasks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "scheduledTasks": [
                    {
                        "id": "integration-task",
                        "name": "Integration task",
                        "prompt": "Run the integration checks",
                        "cronExpression": "*/15 * * * *",
                        "enabled": True,
                    }
                ],
                "recordedSkips": {},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_scheduled_tasks_route_and_guarded_delete(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.webapi import scheduled_tasks_service as service

    claude_root = tmp_path / "Claude"
    codex_home = tmp_path / ".codex"
    task_file = _write_task(claude_root)
    monkeypatch.setattr(service, "_CLAUDE_ROOT", claude_root)
    monkeypatch.setattr(service, "_CODEX_HOME", codex_home)
    _app, client = build_client(app_factory)

    listed = client.get("/api/scheduled-tasks", headers=auth_headers())
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["id"] == "claude:integration-task"

    prepared = client.post(
        "/api/actions/scheduled_tasks.delete/prepare",
        json={"provider": "claude", "task_id": "integration-task"},
        headers=auth_headers(),
    )
    assert prepared.status_code == 200
    ticket = prepared.json()["data"]
    assert ticket["effect_preview"]["removals"]

    executed = client.post(
        "/api/actions/scheduled_tasks.delete/execute",
        json={"ticket_id": ticket["ticket_id"]},
        headers=auth_headers(),
    )
    assert executed.status_code == 200
    assert json.loads(task_file.read_text(encoding="utf-8"))["scheduledTasks"] == []

    refreshed = client.get("/api/scheduled-tasks", headers=auth_headers())
    assert refreshed.json()["data"]["counts"]["all"] == 0


def test_scheduled_tasks_route_requires_auth(app_factory) -> None:
    _app, client = build_client(app_factory)

    response = client.get("/api/scheduled-tasks")

    assert response.status_code == 401
