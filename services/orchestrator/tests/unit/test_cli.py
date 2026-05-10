from __future__ import annotations

import httpx
import pytest
import typer
from rich.console import Console

from orchestrator import cli


class _FakeClient:
    def __init__(self, *, timeout: float) -> None:
        self.timeout = timeout

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def get(self, url: str) -> httpx.Response:
        _CALLED_URLS.append(url)
        return httpx.Response(_STATUS_CODE)


_CALLED_URLS: list[str] = []
_STATUS_CODE = 200


def test_check_a2a_peer_uses_public_agent_card(monkeypatch: pytest.MonkeyPatch) -> None:
    _CALLED_URLS.clear()
    monkeypatch.setattr(cli.httpx, "Client", _FakeClient)

    cli._check_a2a_peer("http://127.0.0.1:8765", Console(stderr=True))

    assert _CALLED_URLS == ["http://127.0.0.1:8765/.well-known/agent-card.json"]


def test_check_a2a_peer_rejects_non_success_agent_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    global _STATUS_CODE
    _CALLED_URLS.clear()
    _STATUS_CODE = 401
    monkeypatch.setattr(cli.httpx, "Client", _FakeClient)

    try:
        with pytest.raises(typer.Exit) as exc_info:
            cli._check_a2a_peer("http://127.0.0.1:8765", Console(stderr=True))
    finally:
        _STATUS_CODE = 200

    assert exc_info.value.exit_code == 4
