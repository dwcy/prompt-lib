# -*- coding: utf-8 -*-
"""Declarative container service helpers for local database installs."""

from __future__ import annotations

import shutil
import socket
import subprocess
from dataclasses import dataclass, field

from cabal.installers._common import _run_install
from cabal.tool_catalog import redact_secret_text


@dataclass(frozen=True)
class ContainerPort:
    host: int
    container: int
    protocol: str = "tcp"

    def as_arg(self) -> str:
        suffix = "" if self.protocol == "tcp" else f"/{self.protocol}"
        return f"{self.host}:{self.container}{suffix}"


@dataclass(frozen=True)
class ContainerVolume:
    name: str
    target: str

    def as_arg(self) -> str:
        return f"{self.name}:{self.target}"


@dataclass(frozen=True)
class ContainerHealthCheck:
    command: tuple[str, ...]
    timeout_seconds: int = 10


@dataclass(frozen=True)
class ContainerServiceSpec:
    key: str
    image: str
    container_name: str
    ports: tuple[ContainerPort, ...]
    volumes: tuple[ContainerVolume, ...]
    environment: dict[str, str] = field(default_factory=dict)
    command: tuple[str, ...] = ()
    health_check: ContainerHealthCheck | None = None
    logs_hint: str = ""
    cleanup_hint: str = ""
    security_notes: tuple[str, ...] = ()

    def run_command(self, engine: str = "docker") -> list[str]:
        command = [engine, "run", "-d", "--name", self.container_name]
        for port in self.ports:
            command.extend(["-p", port.as_arg()])
        for volume in self.volumes:
            command.extend(["-v", volume.as_arg()])
        for key, value in sorted(self.environment.items()):
            command.extend(["-e", f"{key}={value}"])
        command.append(self.image)
        command.extend(self.command)
        return command

    def status_command(self, engine: str = "docker") -> list[str]:
        return [engine, "inspect", "-f", "{{.State.Status}}", self.container_name]

    def logs_command(self, engine: str = "docker") -> list[str]:
        return [engine, "logs", self.container_name]

    def cleanup_command(self, engine: str = "docker") -> list[str]:
        return [engine, "rm", "-f", self.container_name]


@dataclass(frozen=True)
class EmbeddedDatabaseSpec:
    key: str
    command: tuple[str, ...]
    setup_hint: str
    source_url: str
    file_oriented: bool = True
    daemon_service: bool = False


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    messages: tuple[str, ...]
    engine: str | None = None

    def format(self) -> str:
        return "\n".join(redact_secret_text(message) for message in self.messages)


def detect_container_engine() -> str | None:
    for engine in ("docker", "podman"):
        resolved = shutil.which(engine)
        if not resolved:
            continue
        try:
            result = subprocess.run(
                [resolved, "version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return engine
    return None


def is_host_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _run_engine_command(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess[str] | None:
    head, *rest = args
    resolved = shutil.which(head)
    if not resolved:
        return None
    try:
        return subprocess.run(
            [resolved, *rest],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def container_status(spec: ContainerServiceSpec, engine: str | None = None) -> str | None:
    active_engine = engine or detect_container_engine()
    if not active_engine:
        return None
    result = _run_engine_command(spec.status_command(active_engine))
    if result is None or result.returncode != 0:
        return None
    status = (result.stdout or "").strip()
    return status or None


def container_exists(spec: ContainerServiceSpec, engine: str | None = None) -> bool:
    return container_status(spec, engine) is not None


def preflight_container_service(
    spec: ContainerServiceSpec,
    *,
    engine: str | None = None,
) -> PreflightResult:
    active_engine = engine or detect_container_engine()
    messages: list[str] = []
    if not active_engine:
        return PreflightResult(
            False,
            ("Container engine missing or stopped. Install and start Docker or Podman first.",),
            None,
        )

    messages.append(f"Container engine ready: {active_engine}")
    for port in spec.ports:
        if not is_host_port_available(port.host):
            messages.append(f"Port conflict: host port {port.host} is already in use.")
    if container_exists(spec, active_engine):
        messages.append(f"Existing instance detected: {spec.container_name}.")
    if any(message.startswith(("Port conflict", "Existing instance")) for message in messages):
        return PreflightResult(False, tuple(messages), active_engine)

    messages.append(f"Image: {spec.image}")
    messages.append("Ports: " + ", ".join(port.as_arg() for port in spec.ports))
    messages.append("Volumes: " + ", ".join(volume.as_arg() for volume in spec.volumes))
    return PreflightResult(True, tuple(messages), active_engine)


def run_health_check(spec: ContainerServiceSpec, engine: str) -> tuple[bool, str]:
    if spec.health_check is None:
        return True, "No explicit health check configured; container start completed."
    result = _run_engine_command([engine, *spec.health_check.command], timeout=spec.health_check.timeout_seconds)
    if result is None:
        return False, "Health check could not be launched."
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    return result.returncode == 0, output or "health check completed"


def install_container_service(spec: ContainerServiceSpec) -> tuple[bool, str]:
    preflight = preflight_container_service(spec)
    if not preflight.ok:
        return False, preflight.format()
    assert preflight.engine is not None

    pull_ok, pull_msg = _run_install([preflight.engine, "pull", spec.image])
    if not pull_ok:
        return False, redact_secret_text(f"Image pull failed for {spec.image}\n{pull_msg}")

    run_ok, run_msg = _run_install(spec.run_command(preflight.engine))
    if not run_ok:
        return False, redact_secret_text(f"Container start failed for {spec.container_name}\n{run_msg}")

    healthy, health_msg = run_health_check(spec, preflight.engine)
    if not healthy:
        return False, redact_secret_text(f"Health check failed for {spec.container_name}\n{health_msg}")

    return (
        True,
        redact_secret_text(
            "\n".join(
                [
                    f"{spec.container_name} is running from {spec.image}.",
                    spec.logs_hint,
                    spec.cleanup_hint,
                ]
            )
        ),
    )
