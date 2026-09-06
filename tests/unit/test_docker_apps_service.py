"""Unit coverage for Docker container discovery and availability states."""

from __future__ import annotations

import json
import subprocess

from cabal.webapi import docker_apps_service


def _result(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(["docker"], returncode, stdout, stderr)


def test_lists_running_and_stopped_compose_containers(monkeypatch) -> None:
    running_id = "a" * 64
    stopped_id = "b" * 64
    rows = [
        {
            "ID": running_id,
            "Names": "web",
            "Image": "fixture/web:latest",
            "State": "running",
            "Status": "Up 2 minutes",
            "HealthStatus": "healthy",
            "Ports": "0.0.0.0:5173->5173/tcp",
        },
        {
            "ID": stopped_id,
            "Names": "worker",
            "Image": "fixture/worker:latest",
            "State": "exited",
            "Status": "Exited (0) 1 hour ago",
            "HealthStatus": "none",
            "Ports": "",
        },
    ]
    labels = [
        {
            "com.docker.compose.project": "fixture",
            "com.docker.compose.service": "web",
            "com.docker.compose.project.working_dir": "C:/projects/fixture",
        },
        {},
    ]

    def fake_run(args: list[str], *, timeout: int = 10):
        del timeout
        if args[:2] == ["container", "ls"]:
            return _result("\n".join(json.dumps(row) for row in rows))
        return _result("\n".join(json.dumps(row) for row in labels))

    monkeypatch.setattr(docker_apps_service.shutil, "which", lambda _name: "docker")
    monkeypatch.setattr(docker_apps_service, "_run_docker", fake_run)

    payload = docker_apps_service.docker_apps_payload()

    assert payload["daemon_running"] is True
    assert payload["counts"] == {"total": 2, "running": 1, "stopped": 1, "other": 0}
    assert payload["containers"][0]["location"] == "C:/projects/fixture"
    assert payload["containers"][0]["can_stop"] is True
    assert payload["containers"][1]["can_start"] is True


def test_reports_missing_cli_without_failing_the_api(monkeypatch) -> None:
    monkeypatch.setattr(docker_apps_service.shutil, "which", lambda _name: None)

    payload = docker_apps_service.docker_apps_payload()

    assert payload["available"] is False
    assert payload["daemon_running"] is False
    assert payload["containers"] == []
    assert payload["message"] == "Docker CLI is not installed"


def test_reports_stopped_daemon_without_failing_the_api(monkeypatch) -> None:
    monkeypatch.setattr(docker_apps_service.shutil, "which", lambda _name: "docker")
    monkeypatch.setattr(
        docker_apps_service,
        "_run_docker",
        lambda _args: _result(stderr="Cannot connect to the Docker daemon", returncode=1),
    )

    payload = docker_apps_service.docker_apps_payload()

    assert payload["available"] is True
    assert payload["daemon_running"] is False
    assert payload["message"] == "Cannot connect to the Docker daemon"
