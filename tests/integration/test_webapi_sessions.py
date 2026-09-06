"""Large transcript-set integration coverage for the paginated sessions API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contract.webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]


def test_thousand_session_fixture_stays_page_bounded_with_correct_totals(
    app_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cabal import session_reader

    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "prompt-lib"
    project_dir.mkdir(parents=True)
    for index in range(1_000):
        entry = {
            "type": "assistant",
            "timestamp": f"2026-07-{1 + index % 19:02d}T10:00:00Z",
            "message": {
                "role": "assistant",
                "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": f"Session {index}"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        }
        (project_dir / f"session-{index:04d}.jsonl").write_text(
            json.dumps(entry) + "\n", encoding="utf-8"
        )
    monkeypatch.setattr(session_reader, "_PROJECTS_DIR", projects_dir)
    _app, client = build_client(app_factory)

    first = client.get("/api/sessions?limit=100", headers=auth_headers()).json()["data"]
    second = client.get(
        f"/api/sessions?limit=100&cursor={first['next_cursor']}", headers=auth_headers()
    ).json()["data"]

    assert first["totals"]["session_count"] == 1_000
    assert first["totals"]["tokens_in"] == 10_000
    assert first["totals"]["tokens_out"] == 5_000
    assert len(first["items"]) == len(second["items"]) == 100
    assert first["page_size"] == second["page_size"] == 100
    assert first["next_cursor"] == "100"
    assert second["next_cursor"] == "200"
    assert {row["session_id"] for row in first["items"]}.isdisjoint(
        row["session_id"] for row in second["items"]
    )
