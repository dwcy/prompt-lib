"""Init-project preview, apply, handoff streaming, and cancellation integration."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from contract.webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]


class _FakeStdout:
    def __init__(self, process: "_FakeHandoffProcess") -> None:
        self.process = process
        self.lines = 0

    def readline(self) -> str:
        if self.process.returncode is not None:
            return ""
        time.sleep(0.03)
        self.lines += 1
        if self.lines > 200:
            self.process.returncode = 0
            return ""
        return f"fake handoff line {self.lines}\n"


class _FakeHandoffProcess:
    def __init__(self) -> None:
        self.returncode: int | None = None
        self.stdout = _FakeStdout(self)
        self.terminated = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def kill(self) -> None:
        self.terminated = True
        self.returncode = -9


def _prepare_execute(client, action_id: str, params: dict) -> dict:
    prepared = client.post(
        f"/api/actions/{action_id}/prepare", json=params, headers=auth_headers()
    )
    assert prepared.status_code == 200, prepared.text
    executed = client.post(
        f"/api/actions/{action_id}/execute",
        json={"ticket_id": prepared.json()["data"]["ticket_id"]},
        headers=auth_headers(),
    )
    assert executed.status_code in {200, 202}, executed.text
    return executed.json()["data"]


def test_init_plan_apply_and_cancel_fake_handoff(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.init_project_service import LocalTemplateRef
    from cabal.webapi.routers import projects as projects_router

    template_file = tmp_path / "template.md"
    template_file.write_text("# Generated fixture\n", encoding="utf-8")
    monkeypatch.setattr(
        projects_router,
        "_local_template_refs",
        lambda: [LocalTemplateRef(stem="fixture", path=template_file)],
    )
    monkeypatch.setattr(projects_router.shutil, "which", lambda command: command)
    handoff = _FakeHandoffProcess()
    monkeypatch.setattr(projects_router, "spawn_claude", lambda **_kwargs: handoff)
    _app, client = build_client(app_factory)
    params = {
        "dest": str(tmp_path),
        "name": "generated-project",
        "template": "local:fixture",
        "selected_files": ["CLAUDE.md"],
        "run_claude": True,
        "mcp_json": '{"mcpServers": {"fixture": {"command": "fixture"}}}',
    }

    plan = client.get(
        "/api/init/plan",
        params={"dest": params["dest"], "name": params["name"], "template": params["template"]},
        headers=auth_headers(),
    )
    assert plan.status_code == 200
    assert plan.json()["data"]["name_valid"] is True
    assert any(row["rel_path"] == "CLAUDE.md" for row in plan.json()["data"]["staged_files"])

    job_id = _prepare_execute(client, "init.apply", params)["job_id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        record = client.get(f"/api/jobs/{job_id}", headers=auth_headers()).json()["data"]
        if any("Starting claude handoff" in line for line in record["output_tail"]):
            break
        time.sleep(0.02)
    else:
        pytest.fail("init job never reached the fake handoff")

    cancelled = _prepare_execute(client, "jobs.cancel", {"job_id": job_id})
    assert cancelled["state"] == "cancelled"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        record = client.get(f"/api/jobs/{job_id}", headers=auth_headers()).json()["data"]
        if record["state"] == "cancelled" and handoff.terminated:
            break
        time.sleep(0.02)

    target = tmp_path / "generated-project"
    assert record["state"] == "cancelled"
    assert handoff.terminated is True
    assert (target / "CLAUDE.md").read_text(encoding="utf-8") == "# Generated fixture\n"
    assert (target / ".mcp.json").is_file()
    assert (target / ".claude" / "INIT_PROMPT.md").is_file()
    assert _app.state.project != target
