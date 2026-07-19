"""Integration coverage for app-owned service lifecycle, logs, and shutdown cleanup."""

from __future__ import annotations

from pathlib import Path

import pytest

from contract.webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]


class _FakeProcess:
    _next_pid = 4_200

    def __init__(self, _command, *, stdout, **_kwargs) -> None:
        type(self)._next_pid += 1
        self.pid = type(self)._next_pid
        self._returncode: int | None = None
        self.terminated = False
        stdout.write("fixture service ready\n")
        stdout.flush()

    def poll(self) -> int | None:
        return self._returncode

    def terminate(self) -> None:
        self.terminated = True
        self._returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        return self._returncode or 0

    def kill(self) -> None:
        self.terminated = True
        self._returncode = -9


def _execute_action(client, action_id: str, params: dict) -> dict:
    prepared = client.post(
        f"/api/actions/{action_id}/prepare", json=params, headers=auth_headers()
    )
    assert prepared.status_code == 200, prepared.text
    ticket_id = prepared.json()["data"]["ticket_id"]
    executed = client.post(
        f"/api/actions/{action_id}/execute",
        json={"ticket_id": ticket_id},
        headers=auth_headers(),
    )
    assert executed.status_code == 200, executed.text
    return executed.json()["data"]


def test_service_start_stream_stop_and_app_shutdown_cleanup(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal import service_supervisor
    from cabal.webapi.routers import services as services_router

    service_supervisor.shutdown_all()
    service_supervisor._STATES.clear()
    services_router._LOG_STATES.clear()
    monkeypatch.setattr(service_supervisor, "_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(service_supervisor, "is_set_up", lambda _key: True)
    monkeypatch.setattr(service_supervisor.service_prereqs, "check", lambda _key: [])
    monkeypatch.setattr(service_supervisor, "_port_running", lambda _definition: False)
    monkeypatch.setattr(service_supervisor.shutil, "which", lambda command: command)
    spawned: list[_FakeProcess] = []

    def fake_popen(command, **kwargs):
        process = _FakeProcess(command, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(service_supervisor.subprocess, "Popen", fake_popen)
    _app, client = build_client(app_factory)

    started = _execute_action(client, "services.start", {"key": "a2a-bridge"})
    assert started["service"]["state"] == "running"
    assert started["service"]["started_by_app"] is True

    stream = client.get(
        "/api/services/a2a-bridge/logs/stream",
        headers={**auth_headers(), "Accept": "text/event-stream"},
    )
    assert stream.status_code == 200
    assert "fixture service ready" in stream.text

    stopped = _execute_action(client, "services.stop", {"key": "a2a-bridge"})
    assert stopped["service"]["state"] == "stopped"
    assert spawned[0].terminated is True

    _execute_action(client, "services.start", {"key": "a2a-bridge"})
    shutdown = client.post("/api/system/shutdown", headers=auth_headers())

    assert shutdown.status_code == 200
    assert shutdown.json()["data"]["stopping"] is True
    assert spawned[-1].terminated is True
    assert service_supervisor._PROCS == {}
