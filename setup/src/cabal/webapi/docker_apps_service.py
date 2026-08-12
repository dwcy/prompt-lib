"""Read and control local Docker containers through the Docker CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from cabal.webapi.envelope import ApiError, compute_precondition_digest

_STOPPABLE_STATES = {"running", "paused", "restarting"}
_STARTABLE_STATES = {"created", "exited"}
_COMPOSE_PROJECT = "com.docker.compose.project"
_COMPOSE_SERVICE = "com.docker.compose.service"
_COMPOSE_WORKING_DIR = "com.docker.compose.project.working_dir"


def docker_apps_payload() -> dict[str, Any]:
    """Return all local Docker containers and an explicit engine availability state."""
    if shutil.which("docker") is None:
        return _unavailable_payload("Docker CLI is not installed", available=False)

    try:
        result = _run_docker(
            ["container", "ls", "--all", "--no-trunc", "--format", "{{json .}}"]
        )
    except subprocess.TimeoutExpired:
        return _unavailable_payload("Docker did not respond", available=True)
    except OSError as exc:
        return _unavailable_payload(str(exc), available=False)

    if result.returncode != 0:
        message = _command_error(result, "Docker engine is unavailable")
        return _unavailable_payload(message, available=True)

    raw_rows = _json_lines(result.stdout)
    labels_by_id = _inspect_labels([str(row.get("ID", "")) for row in raw_rows])
    containers = [
        _container_row(row, labels_by_id.get(str(row.get("ID", "")), {}))
        for row in raw_rows
        if row.get("ID")
    ]
    containers.sort(key=lambda row: (row["name"].casefold(), row["container_id"]))
    return {
        "available": True,
        "daemon_running": True,
        "message": None,
        "containers": containers,
        "counts": {
            "total": len(containers),
            "running": sum(1 for row in containers if row["state"] == "running"),
            "stopped": sum(1 for row in containers if row["state"] in _STARTABLE_STATES),
            "other": sum(
                1
                for row in containers
                if row["state"] not in _STARTABLE_STATES | {"running"}
            ),
        },
    }


def find_docker_container(
    container_id: str, expected_state: str | None = None
) -> dict[str, Any]:
    payload = docker_apps_payload()
    if not payload["daemon_running"]:
        raise ApiError(503, "docker_unavailable", payload["message"] or "Docker is unavailable")
    matches = [
        row
        for row in payload["containers"]
        if row["container_id"] == container_id or row["container_id"].startswith(container_id)
    ]
    if len(matches) != 1:
        raise ApiError(404, "docker_container_not_found", f"Unknown Docker container {container_id!r}")
    container = matches[0]
    if expected_state is not None and container["state"] != expected_state:
        raise ApiError(
            409,
            "state_changed",
            f"Docker container state changed from {expected_state} to {container['state']}",
        )
    return container


def docker_container_digest(container_id: str, expected_state: str) -> str:
    container = find_docker_container(container_id, expected_state)
    return compute_precondition_digest(
        {"container_id": container["container_id"], "state": container["state"]}
    )


def start_docker_container(container_id: str, expected_state: str) -> dict[str, Any]:
    container = find_docker_container(container_id, expected_state)
    if container["state"] not in _STARTABLE_STATES:
        raise ApiError(422, "docker_container_not_startable", "This container cannot be started")
    _run_container_action(["container", "start", container["container_id"]], "start")
    return {"started": True, "container": find_docker_container(container["container_id"])}


def stop_docker_container(container_id: str, expected_state: str) -> dict[str, Any]:
    container = find_docker_container(container_id, expected_state)
    if container["state"] not in _STOPPABLE_STATES:
        raise ApiError(422, "docker_container_not_stoppable", "This container cannot be stopped")
    _run_container_action(
        ["container", "stop", "--time", "10", container["container_id"]], "stop"
    )
    return {"stopped": True, "container": find_docker_container(container["container_id"])}


def _run_container_action(args: list[str], verb: str) -> None:
    try:
        result = _run_docker(args, timeout=20)
    except subprocess.TimeoutExpired as exc:
        raise ApiError(504, "docker_timeout", f"Docker did not {verb} the container in time") from exc
    except OSError as exc:
        raise ApiError(503, "docker_unavailable", str(exc)) from exc
    if result.returncode != 0:
        raise ApiError(409, f"docker_{verb}_failed", _command_error(result, f"Docker {verb} failed"))


def _run_docker(args: list[str], *, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _json_lines(output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _inspect_labels(container_ids: list[str]) -> dict[str, dict[str, str]]:
    ids = [container_id for container_id in container_ids if container_id]
    if not ids:
        return {}
    try:
        result = _run_docker(
            ["container", "inspect", "--format", "{{json .Config.Labels}}", *ids]
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if result.returncode != 0:
        return {}
    label_rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = {}
        label_rows.append(value if isinstance(value, dict) else {})
    return {
        container_id: {
            str(key): str(value)
            for key, value in labels.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        for container_id, labels in zip(ids, label_rows, strict=False)
    }


def _container_row(raw: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    state = str(raw.get("State", "unknown")).casefold()
    return {
        "container_id": str(raw["ID"]),
        "name": str(raw.get("Names") or raw["ID"][:12]),
        "image": str(raw.get("Image") or "unknown"),
        "state": state,
        "status": str(raw.get("Status") or state),
        "health": _nullable_string(raw.get("HealthStatus"), ignored={"none"}),
        "ports": str(raw.get("Ports") or ""),
        "project": labels.get(_COMPOSE_PROJECT),
        "service": labels.get(_COMPOSE_SERVICE),
        "location": labels.get(_COMPOSE_WORKING_DIR),
        "can_start": state in _STARTABLE_STATES,
        "can_stop": state in _STOPPABLE_STATES,
    }


def _nullable_string(value: Any, *, ignored: frozenset[str] = frozenset()) -> str | None:
    text = str(value or "").strip()
    return None if not text or text.casefold() in ignored else text


def _unavailable_payload(message: str, *, available: bool) -> dict[str, Any]:
    return {
        "available": available,
        "daemon_running": False,
        "message": message,
        "containers": [],
        "counts": {"total": 0, "running": 0, "stopped": 0, "other": 0},
    }


def _command_error(result: subprocess.CompletedProcess[str], fallback: str) -> str:
    message = (result.stderr or result.stdout).strip()
    return message.splitlines()[-1] if message else fallback
