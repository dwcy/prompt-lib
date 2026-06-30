"""Unit tests for cabal.service_prereqs — per-service prerequisite probes (T013).

Exercises the read-only check()/blocking() boundary hermetically: the bearer-token
env var, the a2a-peer port probe, and the gh-auth subprocess are all controlled via
monkeypatch so no real network, gh CLI, or environment leakage affects the result.
"""

from __future__ import annotations

import subprocess

import pytest

from cabal import service_prereqs
from cabal.service_prereqs import blocking, check

_A2A_TOKEN_ENV = "A2A_BEARER_TOKEN"


def _by_name(results, name):
    return next(result for result in results if result.name == name)


# ------------------------------------------------------------------
# a2a-bridge: A2A_BEARER_TOKEN env prerequisite
# ------------------------------------------------------------------


def test_a2a_bridge_missing_token_is_blocking_with_message(monkeypatch):
    monkeypatch.delenv(_A2A_TOKEN_ENV, raising=False)

    results = check("a2a-bridge")
    token = _by_name(results, _A2A_TOKEN_ENV)

    assert token.ok is False
    assert token.message.strip()
    assert any(r.name == _A2A_TOKEN_ENV for r in blocking(results))


def test_a2a_bridge_present_token_is_satisfied(monkeypatch):
    monkeypatch.setenv(_A2A_TOKEN_ENV, "secret-token")

    results = check("a2a-bridge")
    token = _by_name(results, _A2A_TOKEN_ENV)

    assert token.ok is True
    assert all(r.name != _A2A_TOKEN_ENV for r in blocking(results))


# ------------------------------------------------------------------
# orchestrator: a2a-peer port probe + gh-auth (both kept hermetic)
# ------------------------------------------------------------------


@pytest.fixture
def gh_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend gh is installed and authenticated without touching the real CLI."""
    monkeypatch.setattr(service_prereqs.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        service_prereqs.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            args=a, returncode=0, stdout="", stderr=""
        ),
    )


def test_orchestrator_a2a_peer_down_is_blocking(monkeypatch, gh_authenticated):
    monkeypatch.setattr(service_prereqs, "_port_open", lambda _port: False)

    results = check("orchestrator")
    peer = _by_name(results, "a2a-peer")

    assert peer.ok is False
    assert "Start a2a-bridge first" in peer.message
    assert any(r.name == "a2a-peer" for r in blocking(results))


def test_orchestrator_a2a_peer_up_is_satisfied(monkeypatch, gh_authenticated):
    monkeypatch.setattr(service_prereqs, "_port_open", lambda _port: True)

    results = check("orchestrator")
    peer = _by_name(results, "a2a-peer")

    assert peer.ok is True
    assert all(r.name != "a2a-peer" for r in blocking(results))


def test_orchestrator_gh_authenticated_is_satisfied(monkeypatch, gh_authenticated):
    monkeypatch.setattr(service_prereqs, "_port_open", lambda _port: True)

    results = check("orchestrator")
    gh = _by_name(results, "gh-auth")

    assert gh.ok is True


def test_orchestrator_gh_unauthenticated_is_blocking(monkeypatch):
    monkeypatch.setattr(service_prereqs.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        service_prereqs.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            args=a, returncode=1, stdout="", stderr=""
        ),
    )
    monkeypatch.setattr(service_prereqs, "_port_open", lambda _port: True)

    results = check("orchestrator")
    gh = _by_name(results, "gh-auth")

    assert gh.ok is False
    assert gh.message.strip()
    assert any(r.name == "gh-auth" for r in blocking(results))


def test_orchestrator_gh_missing_binary_is_blocking(monkeypatch):
    monkeypatch.setattr(service_prereqs.shutil, "which", lambda name: None)
    monkeypatch.setattr(service_prereqs, "_port_open", lambda _port: True)

    results = check("orchestrator")
    gh = _by_name(results, "gh-auth")

    assert gh.ok is False
    assert gh.message.strip()


def test_orchestrator_ntfy_is_non_blocking(monkeypatch, gh_authenticated):
    monkeypatch.setattr(service_prereqs, "_port_open", lambda _port: True)

    results = check("orchestrator")
    ntfy = _by_name(results, "ntfy")

    assert ntfy.ok is True
    assert all(r.name != "ntfy" for r in blocking(results))
