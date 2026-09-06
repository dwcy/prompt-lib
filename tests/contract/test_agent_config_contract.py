# -*- coding: utf-8 -*-
"""Contract suite for the Agent Setup module: agent_config_service's tree walker and file
reader (unit-level, real tmp_path fixtures), plus /api/agent-config/{tree,file} for the
local-scope path (which does not depend on this machine's real home directory)."""

from __future__ import annotations

from pathlib import Path

import pytest

from .webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]


def _service():
    from cabal.webapi import agent_config_service

    return agent_config_service


# -- build_agent_config_tree ---------------------------------------------


def test_claude_global_tree_lists_dirs_before_files_alphabetically(tmp_path: Path) -> None:
    service = _service()
    claude_home = tmp_path / "claude-home"
    (claude_home / "agents").mkdir(parents=True)
    (claude_home / "agents" / "one.md").write_text("one", encoding="utf-8")
    (claude_home / "CLAUDE.md").write_text("root instructions", encoding="utf-8")
    (claude_home / "hooks").mkdir()

    data = service.build_agent_config_tree("claude", "global", None, claude_target=claude_home)

    assert data["exists"] is True
    kinds = [(entry["name"], entry["kind"]) for entry in data["roots"]]
    assert kinds == [("agents", "dir"), ("hooks", "dir"), ("CLAUDE.md", "file")]
    assert data["roots"][0]["children"][0]["rel_path"] == "agents/one.md"


def test_claude_local_scope_walks_project_dot_claude(tmp_path: Path) -> None:
    service = _service()
    project = tmp_path / "my-project"
    (project / ".claude").mkdir(parents=True)
    (project / ".claude" / "CLAUDE.md").write_text("local", encoding="utf-8")

    data = service.build_agent_config_tree("claude", "local", project)

    assert data["exists"] is True
    assert [entry["name"] for entry in data["roots"]] == ["CLAUDE.md"]


def test_claude_local_scope_without_a_project_raises_no_project_selected(tmp_path: Path) -> None:
    from cabal.webapi.envelope import ApiError

    service = _service()
    with pytest.raises(ApiError) as excinfo:
        service.build_agent_config_tree("claude", "local", None)
    assert excinfo.value.code == "no_project_selected"


def test_codex_and_antigravity_local_scope_only_show_the_shared_agents_md_roots(
    tmp_path: Path,
) -> None:
    service = _service()
    project = tmp_path / "my-project"
    (project / ".agents").mkdir(parents=True)
    (project / ".agents" / "rules.md").write_text("rules", encoding="utf-8")
    (project / "AGENTS.md").write_text("shared", encoding="utf-8")
    (project / "unrelated.txt").write_text("not part of the browsed roots", encoding="utf-8")

    for agent in ("codex", "antigravity"):
        data = service.build_agent_config_tree(agent, "local", project)
        names = {entry["name"] for entry in data["roots"]}
        assert names == {".agents", "AGENTS.md"}


def test_codex_global_scope_uses_the_injected_codex_dir(tmp_path: Path) -> None:
    service = _service()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text("[settings]", encoding="utf-8")

    data = service.build_agent_config_tree("codex", "global", None, codex_dir=codex_home)

    assert data["exists"] is True
    assert data["base_path"] == str(codex_home)


def test_antigravity_global_scope_uses_the_injected_gemini_dir(tmp_path: Path) -> None:
    service = _service()
    gemini_home = tmp_path / "gemini-home"
    gemini_home.mkdir()

    data = service.build_agent_config_tree("antigravity", "global", None, gemini_dir=gemini_home)

    assert data["exists"] is True
    assert data["base_path"] == str(gemini_home)


def test_missing_base_dir_reports_exists_false_instead_of_erroring(tmp_path: Path) -> None:
    service = _service()
    data = service.build_agent_config_tree("claude", "global", None, claude_target=tmp_path / "nope")
    assert data == {
        "agent": "claude",
        "scope": "global",
        "base_path": str(tmp_path / "nope"),
        "exists": False,
        "roots": [],
        "truncated": False,
    }


def test_walk_caps_entries_and_reports_truncated(tmp_path: Path, monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(service, "MAX_ENTRIES", 3)
    claude_home = tmp_path / "claude-home"
    claude_home.mkdir()
    for index in range(10):
        (claude_home / f"file-{index}.md").write_text("x", encoding="utf-8")

    data = service.build_agent_config_tree("claude", "global", None, claude_target=claude_home)

    assert data["truncated"] is True
    assert len(data["roots"]) <= 3


# -- read_agent_config_file ------------------------------------------------


def test_reading_a_text_file_returns_its_content(tmp_path: Path) -> None:
    service = _service()
    claude_home = tmp_path / "claude-home"
    claude_home.mkdir()
    (claude_home / "CLAUDE.md").write_text("hello world", encoding="utf-8")

    data = service.read_agent_config_file(
        "claude", "global", None, "CLAUDE.md", claude_target=claude_home
    )

    assert data == {
        "rel_path": "CLAUDE.md",
        "content": "hello world",
        "binary": False,
        "truncated": False,
        "size_bytes": len(b"hello world"),
    }


def test_reading_a_binary_file_reports_binary_with_no_content(tmp_path: Path) -> None:
    service = _service()
    claude_home = tmp_path / "claude-home"
    claude_home.mkdir()
    (claude_home / "blob.bin").write_bytes(b"\x00\x01\x02binary")

    data = service.read_agent_config_file(
        "claude", "global", None, "blob.bin", claude_target=claude_home
    )

    assert data["binary"] is True
    assert data["content"] is None


def test_reading_an_oversized_file_truncates_the_preview(tmp_path: Path, monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(service, "MAX_PREVIEW_BYTES", 10)
    claude_home = tmp_path / "claude-home"
    claude_home.mkdir()
    (claude_home / "big.md").write_text("0123456789ABCDEF", encoding="utf-8")

    data = service.read_agent_config_file(
        "claude", "global", None, "big.md", claude_target=claude_home
    )

    assert data["truncated"] is True
    assert data["content"] == "0123456789"
    assert data["size_bytes"] == len("0123456789ABCDEF")


def test_path_traversal_outside_the_config_root_is_rejected(tmp_path: Path) -> None:
    from cabal.webapi.envelope import ApiError

    service = _service()
    claude_home = tmp_path / "claude-home"
    claude_home.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("nope", encoding="utf-8")

    with pytest.raises(ApiError) as excinfo:
        service.read_agent_config_file(
            "claude", "global", None, "../secret.txt", claude_target=claude_home
        )
    assert excinfo.value.code == "path_outside_root"


def test_codex_local_file_read_outside_the_browsed_roots_is_rejected(tmp_path: Path) -> None:
    from cabal.webapi.envelope import ApiError

    service = _service()
    project = tmp_path / "my-project"
    project.mkdir()
    (project / ".env").write_text("SECRET=1", encoding="utf-8")

    with pytest.raises(ApiError) as excinfo:
        service.read_agent_config_file("codex", "local", project, ".env")
    assert excinfo.value.code == "path_outside_root"


# -- HTTP surface (local scope only -- global scope depends on this machine's real home dir) --


def test_http_tree_route_serves_claude_local_scope(app_factory, tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "CLAUDE.md").write_text("hi", encoding="utf-8")
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.get(
        "/api/agent-config/tree", params={"agent": "claude", "scope": "local"}, headers=auth_headers()
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "agent_config"
    assert body["data"]["exists"] is True


def test_http_tree_route_without_a_selected_project_returns_404(app_factory, tmp_path: Path) -> None:
    _app, client = build_client(app_factory, project=None)

    response = client.get(
        "/api/agent-config/tree", params={"agent": "claude", "scope": "local"}, headers=auth_headers()
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_project_selected"


def test_http_file_route_serves_claude_local_file_content(app_factory, tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "CLAUDE.md").write_text("hi there", encoding="utf-8")
    _app, client = build_client(app_factory, project=tmp_path)

    response = client.get(
        "/api/agent-config/file",
        params={"agent": "claude", "scope": "local", "rel_path": "CLAUDE.md"},
        headers=auth_headers(),
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["content"] == "hi there"
