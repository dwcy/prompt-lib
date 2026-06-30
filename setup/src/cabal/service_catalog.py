# -*- coding: utf-8 -*-
"""Static registry of the local agent services surfaced in the Cabal UI (data only)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

REPO_URL = "https://github.com/dwcy/prompt-lib"


class ServiceStatus(StrEnum):
    NOT_SET_UP = "not_set_up"
    STOPPED = "stopped"
    RUNNING = "running"
    BLOCKED = "blocked"
    INFO_ONLY = "info_only"


class InstallKind(StrEnum):
    UV_TOOL = "uv_tool"


@dataclass(frozen=True)
class ServiceDefinition:
    key: str
    label: str
    description: str
    run_command: str
    source_url: str
    runnable: bool
    depends_on: tuple[str, ...]
    install_path: str
    console_name: str
    prereq_keys: tuple[str, ...]
    dashboard_command: str | None
    log_hint: str | None
    default_port: int | None
    install_kind: InstallKind = InstallKind.UV_TOOL


@dataclass
class ServiceState:
    key: str
    status: ServiceStatus
    pid: int | None = None
    started_by_cabal: bool = False
    detail: str = ""


@dataclass
class PrereqResult:
    name: str
    ok: bool
    message: str


def _source(subdir: str) -> str:
    return f"{REPO_URL}/tree/main/services/{subdir}"


SERVICE_DEFINITIONS: tuple[ServiceDefinition, ...] = (
    ServiceDefinition(
        key="a2a-bridge",
        label="A2A Bridge",
        description="Local Agent-to-Agent HTTP bridge that fronts a CLI agent (claude/gemini) as an A2A peer for the orchestrator.",
        run_command="a2a-bridge serve",
        source_url=_source("a2a-bridge"),
        runnable=True,
        depends_on=(),
        install_path="services/a2a-bridge",
        console_name="a2a-bridge",
        prereq_keys=("A2A_BEARER_TOKEN", "agent-target"),
        dashboard_command=None,
        log_hint="Activity is on the server's stdout where `a2a-bridge serve` runs (port 8765).",
        default_port=8765,
    ),
    ServiceDefinition(
        key="orchestrator",
        label="Orchestrator",
        description="Polls GitHub for work, delegates to A2A peer agents, and tracks runs in a local SQLite event log.",
        run_command="orchestrator serve",
        source_url=_source("orchestrator"),
        runnable=True,
        depends_on=("a2a-bridge",),
        install_path="services/orchestrator",
        console_name="orchestrator",
        prereq_keys=("gh-auth", "ntfy", "a2a-peer"),
        dashboard_command="orchestrator dash",
        log_hint=None,
        default_port=None,
    ),
    ServiceDefinition(
        key="mcp-bus",
        label="MCP Bus",
        description="Client-launched stdio MCP server: agent message bus, shared memory, and registry. Started on demand by its MCP clients, not as a standalone daemon.",
        run_command="mcp-bus",
        source_url=f"{REPO_URL}/tree/main/services/mcp-bus",
        runnable=False,
        depends_on=(),
        install_path="services/mcp-bus",
        console_name="mcp-bus",
        prereq_keys=(),
        dashboard_command=None,
        log_hint=None,
        default_port=None,
    ),
)


SERVICE_BY_KEY: dict[str, ServiceDefinition] = {
    service.key: service for service in SERVICE_DEFINITIONS
}


def all_services() -> tuple[ServiceDefinition, ...]:
    return SERVICE_DEFINITIONS


def get_service(key: str) -> ServiceDefinition:
    return SERVICE_BY_KEY[key]


def validate_catalog() -> None:
    """Enforce the data-model validation rules; raise ValueError on any breach."""
    if len(SERVICE_DEFINITIONS) != 3:
        raise ValueError(
            f"expected exactly 3 services, found {len(SERVICE_DEFINITIONS)}"
        )

    required_fields = (
        "key",
        "label",
        "description",
        "run_command",
        "source_url",
        "console_name",
        "install_path",
    )
    for service in SERVICE_DEFINITIONS:
        for name in required_fields:
            if not str(getattr(service, name)).strip():
                raise ValueError(f"{service.key or '<unknown>'}: empty {name}")
        if not service.runnable and service.dashboard_command is not None:
            raise ValueError(
                f"{service.key}: non-runnable service must have dashboard_command=None"
            )
        for dependency in service.depends_on:
            if dependency not in SERVICE_BY_KEY:
                raise ValueError(
                    f"{service.key}: depends_on '{dependency}' is not a defined service"
                )
