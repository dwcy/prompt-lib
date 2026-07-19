"""Integration tests for US3 config actions: stale apply protection, cleanup
round-trip, and settings override idempotence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contract.webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]


@pytest.fixture
def isolated_config_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    source = tmp_path / "global"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()

    from cabal import claude_settings, cleanup_service, components, diff_apply
    from cabal.webapi import config_service
    from cabal.webapi.actions_catalog import config as config_actions

    monkeypatch.setattr(components, "GLOBAL_DIR", source)
    monkeypatch.setattr(components, "TARGET", target)
    monkeypatch.setattr(diff_apply, "TARGET", target)
    monkeypatch.setattr(cleanup_service, "TARGET", target)
    monkeypatch.setattr(claude_settings, "GLOBAL_DIR", source)
    monkeypatch.setattr(claude_settings, "TARGET", target)
    monkeypatch.setattr(config_service, "TARGET", target)
    monkeypatch.setattr(config_actions, "TARGET", target)
    return source, target


def _prepare(client, action_id: str, params: dict) -> dict:
    response = client.post(f"/api/actions/{action_id}/prepare", json=params, headers=auth_headers())
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _execute(client, action_id: str, ticket_id: str):
    return client.post(
        f"/api/actions/{action_id}/execute",
        json={"ticket_id": ticket_id},
        headers=auth_headers(),
    )


def test_ConfigApply_mutated_source_returns_409_and_does_not_write(
    app_factory, isolated_config_roots: tuple[Path, Path]
) -> None:
    source, target = isolated_config_roots
    (source / "CLAUDE.md").write_text("source v1\n", encoding="utf-8")
    _app, client = build_client(app_factory)

    ticket = _prepare(client, "config.apply", {"target": "claude", "paths": ["CLAUDE.md"]})
    (source / "CLAUDE.md").write_text("source v2\n", encoding="utf-8")

    response = _execute(client, "config.apply", ticket["ticket_id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "state_changed"
    assert not (target / "CLAUDE.md").exists()


def test_ConfigCleanup_backup_remove_restore_round_trip(
    app_factory, isolated_config_roots: tuple[Path, Path]
) -> None:
    source, target = isolated_config_roots
    (source / "skills").mkdir()
    extra = target / "skills" / "old-flat-skill.md"
    extra.parent.mkdir(parents=True)
    extra.write_text("stale skill\n", encoding="utf-8")
    _app, client = build_client(app_factory)

    extras = client.get("/api/config/extras?target=claude", headers=auth_headers()).json()["data"]
    rel_paths = [item["rel_path"] for group in extras["groups"] for item in group["extras"]]
    assert rel_paths == ["skills/old-flat-skill.md"]

    cleanup_ticket = _prepare(client, "config.cleanup", {"paths": rel_paths})
    cleanup_response = _execute(client, "config.cleanup", cleanup_ticket["ticket_id"])

    assert cleanup_response.status_code == 200, cleanup_response.text
    backup_id = cleanup_response.json()["data"]["backup_dir"]
    assert backup_id is not None
    assert not extra.exists()
    assert (target / ".cleanup-backups" / backup_id / "skills" / "old-flat-skill.md").read_text(
        encoding="utf-8"
    ) == "stale skill\n"

    restore_ticket = _prepare(client, "config.restore_cleanup", {"backup_id": backup_id})
    restore_response = _execute(client, "config.restore_cleanup", restore_ticket["ticket_id"])

    assert restore_response.status_code == 200, restore_response.text
    assert extra.read_text(encoding="utf-8") == "stale skill\n"


def test_SettingsToggle_same_value_is_idempotent(app_factory, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _app, client = build_client(app_factory, project=project)
    params = {"key": "verbose", "value": True}

    first_ticket = _prepare(client, "settings.toggle", params)
    first_response = _execute(client, "settings.toggle", first_ticket["ticket_id"])
    second_ticket = _prepare(client, "settings.toggle", params)
    second_response = _execute(client, "settings.toggle", second_ticket["ticket_id"])

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    local_settings = json.loads((project / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    assert local_settings["verbose"] is True

    settings = client.get("/api/settings", headers=auth_headers()).json()["data"]["entries"]
    verbose = next(entry for entry in settings if entry["key"] == "verbose")
    assert verbose["source"] == "local_override"
    assert verbose["value_state"] is True
