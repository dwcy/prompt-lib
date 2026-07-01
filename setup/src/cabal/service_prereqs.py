# -*- coding: utf-8 -*-
"""Per-service prerequisite probes and set-up detection (no spawn; read-only checks)."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess

from cabal.service_catalog import PrereqResult, get_service

_A2A_TOKEN_ENV = "A2A_BEARER_TOKEN"
_A2A_BRIDGE_KEY = "a2a-bridge"
_GH_CHECK_TIMEOUT = 10
_PROBE_HOST = "127.0.0.1"
_PROBE_TIMEOUT = 0.25


def is_set_up(key: str) -> bool:
    """True when the service's console command resolves on PATH."""
    return shutil.which(get_service(key).console_name) is not None


def check(key: str) -> list[PrereqResult]:
    """Return one PrereqResult per required prerequisite for the service.

    Performs no mutation and never starts a process. An empty list means the
    service has no prerequisites to satisfy (e.g. the info-only mcp-bus).
    """
    definition = get_service(key)
    if key == _A2A_BRIDGE_KEY:
        return _a2a_bridge_prereqs()
    if key == "orchestrator":
        return _orchestrator_prereqs(definition.default_port)
    return []


def blocking(results: list[PrereqResult]) -> list[PrereqResult]:
    """Filter a check() result down to the unmet (ok is False) prerequisites."""
    return [result for result in results if not result.ok]


def _a2a_bridge_prereqs() -> list[PrereqResult]:
    # The token is non-blocking: cabal injects an ephemeral session token when
    # one is not set (see service_supervisor._child_env), so start never blocks
    # on it. Setting A2A_BEARER_TOKEN yourself gives a stable / networked secret.
    token = os.environ.get(_A2A_TOKEN_ENV)
    return [
        PrereqResult(
            name=_A2A_TOKEN_ENV,
            ok=True,
            message=(
                ""
                if token
                else "No A2A_BEARER_TOKEN set — cabal will use an ephemeral session token "
                "(set one yourself for a stable or network-exposed secret)."
            ),
        ),
        PrereqResult(
            name="agent-target",
            ok=True,
            message="",
        ),
    ]


def _orchestrator_prereqs(a2a_port: int | None) -> list[PrereqResult]:
    return [
        _gh_auth_prereq(),
        _a2a_peer_prereq(a2a_port),
        _ntfy_prereq(),
    ]


def _gh_auth_prereq() -> PrereqResult:
    name = "gh-auth"
    if shutil.which("gh") is None:
        return PrereqResult(
            name=name,
            ok=False,
            message="Install GitHub CLI (gh) and run `gh auth login` before starting orchestrator.",
        )
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GH_CHECK_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return PrereqResult(
            name=name,
            ok=False,
            message="Could not verify gh auth — run `gh auth status` to check your GitHub login.",
        )
    if result.returncode == 0:
        return PrereqResult(name=name, ok=True, message="")
    return PrereqResult(
        name=name,
        ok=False,
        message="GitHub CLI is not authenticated — run `gh auth login` before starting orchestrator.",
    )


def _a2a_peer_prereq(a2a_port: int | None) -> PrereqResult:
    name = "a2a-peer"
    bridge_port = a2a_port if a2a_port is not None else get_service(_A2A_BRIDGE_KEY).default_port
    if bridge_port is not None and _port_open(bridge_port):
        return PrereqResult(name=name, ok=True, message="")
    return PrereqResult(
        name=name,
        ok=False,
        message="Start a2a-bridge first (orchestrator delegates to it).",
    )


def _ntfy_prereq() -> PrereqResult:
    return PrereqResult(
        name="ntfy",
        ok=True,
        message="ntfy is checked by orchestrator at startup; it is non-blocking here.",
    )


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(_PROBE_TIMEOUT)
        return sock.connect_ex((_PROBE_HOST, port)) == 0
