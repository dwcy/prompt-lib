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


def test_running_apps_list_and_confirmed_shutdown_action(
    app_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.webapi.actions_catalog import services as service_actions
    from cabal.webapi.routers import services as services_router

    app = {
        "port": 5_173,
        "pid": 4_242,
        "app_name": "fixture-web",
        "location": "C:/projects/fixture-web",
        "address": "127.0.0.1",
        "started_at": 1_725_000_000.25,
    }
    stopped: list[int] = []
    monkeypatch.setattr(
        services_router,
        "running_apps_payload",
        lambda: {"apps": [app], "count": 1},
    )
    monkeypatch.setattr(service_actions, "find_running_app", lambda *_args: app)
    monkeypatch.setattr(service_actions, "running_app_digest", lambda *_args: "sha256:app")
    monkeypatch.setattr(
        service_actions,
        "stop_running_app",
        lambda pid, _port, _started_at: stopped.append(pid) or {"stopped": True, "app": app},
    )
    _app, client = build_client(app_factory)

    listed = client.get("/api/services/running-apps", headers=auth_headers())
    assert listed.status_code == 200
    assert listed.json()["data"] == {"apps": [app], "count": 1}

    result = _execute_action(
        client,
        "services.running_app.stop",
        {"pid": 4_242, "port": 5_173, "started_at": 1_725_000_000.25},
    )

    assert result["stopped"] is True
    assert stopped == [4_242]


def test_docker_apps_list_start_and_stop_actions(
    app_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal.webapi.actions_catalog import services as service_actions
    from cabal.webapi.routers import services as services_router

    running = {
        "container_id": "a" * 64,
        "name": "fixture-web",
        "image": "fixture/web:latest",
        "state": "running",
        "status": "Up 2 minutes",
        "health": "healthy",
        "ports": "0.0.0.0:5173->5173/tcp",
        "project": "fixture",
        "service": "web",
        "location": "C:/projects/fixture",
        "can_start": False,
        "can_stop": True,
    }
    stopped = running | {
        "container_id": "b" * 64,
        "name": "fixture-worker",
        "state": "exited",
        "status": "Exited (0)",
        "health": None,
        "ports": "",
        "service": "worker",
        "can_start": True,
        "can_stop": False,
    }
    payload = {
        "available": True,
        "daemon_running": True,
        "message": None,
        "containers": [running, stopped],
        "counts": {"total": 2, "running": 1, "stopped": 1, "other": 0},
    }
    lifecycle: list[tuple[str, str]] = []
    monkeypatch.setattr(services_router, "docker_apps_payload", lambda: payload)
    monkeypatch.setattr(
        service_actions,
        "find_docker_container",
        lambda container_id, _expected_state=None: (
            running if container_id.startswith("a") else stopped
        ),
    )
    monkeypatch.setattr(
        service_actions, "docker_container_digest", lambda *_args: "sha256:docker"
    )
    monkeypatch.setattr(
        service_actions,
        "stop_docker_container",
        lambda container_id, _state: lifecycle.append(("stop", container_id))
        or {"stopped": True, "container": stopped},
    )
    monkeypatch.setattr(
        service_actions,
        "start_docker_container",
        lambda container_id, _state: lifecycle.append(("start", container_id))
        or {"started": True, "container": running},
    )
    _app, client = build_client(app_factory)

    listed = client.get("/api/services/docker-apps", headers=auth_headers())
    assert listed.status_code == 200
    assert listed.json()["data"]["counts"]["total"] == 2

    stopped_result = _execute_action(
        client,
        "services.docker.stop",
        {"container_id": running["container_id"], "expected_state": "running"},
    )
    started_result = _execute_action(
        client,
        "services.docker.start",
        {"container_id": stopped["container_id"], "expected_state": "exited"},
    )

    assert stopped_result["stopped"] is True
    assert started_result["started"] is True
    assert lifecycle == [
        ("stop", running["container_id"]),
        ("start", stopped["container_id"]),
    ]
