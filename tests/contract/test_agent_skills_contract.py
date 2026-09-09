# -*- coding: utf-8 -*-
"""Contract suite for the Agent Setup module's Skills view: skill_catalog discovery (personal,
project, plugin), skill_structure's markdown outline / cross-references / bundled files, and
skills_service's precedence + repo-drift payloads. Endpoint tests assert the envelope shape only,
because the routes read this machine's real ~/.claude."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .webapi_fixtures import app_factory, auth_headers, build_client

__all__ = ["app_factory"]

SKILL_BODY = """---
name: demo
description: A demo skill used by the contract suite.
allowed-tools: Bash, Read
---

# Demo skill

Intro paragraph.

## First rule

Do the thing. See `global/hooks/demo.py` and hand off to @python-architect or /git.

```python
value = 1
```

| Scope | Wins |
|---|---|
| project | yes |
| user | no |
"""


def _catalog():
    from cabal import skill_catalog

    return skill_catalog


def _structure():
    from cabal import skill_structure

    return skill_structure


def _service():
    from cabal.webapi import skills_service

    return skills_service


def _write(path: Path, text: str) -> Path:
    """Write exactly the bytes given — newline="" keeps Windows from turning LF into CRLF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


@pytest.fixture
def claude_home(tmp_path: Path) -> Path:
    home = tmp_path / "claude-home"
    _write(home / "skills" / "demo" / "SKILL.md", SKILL_BODY)
    _write(home / "skills" / "demo" / "references" / "notes.md", "# notes\n")
    _write(home / "skills" / "loose.md", "---\nname: loose\n---\n\nignored\n")
    _write(home / "agents" / "python-architect.md", "---\nname: python-architect\n---\n")
    return home


# -- discovery -----------------------------------------------------------


def test_a_skill_folder_is_loaded_and_a_loose_md_file_is_reported_as_ignored(
    claude_home: Path,
) -> None:
    records, _ = _catalog().discover_skills(None, claude_home=claude_home)
    by_name = {record.name: record for record in records}

    assert by_name["demo"].loaded is True
    assert by_name["demo"].invocation == "/demo"
    assert by_name["demo"].allowed_tools == ("Bash", "Read")
    assert by_name["loose"].loaded is False
    assert "SKILL.md" in str(by_name["loose"].not_loaded_reason)


def test_project_skills_and_commands_are_discovered_with_their_own_scope(
    claude_home: Path, tmp_path: Path
) -> None:
    project = tmp_path / "repo"
    _write(project / ".claude" / "skills" / "local" / "SKILL.md", "---\nname: local\n---\n")
    _write(project / ".claude" / "commands" / "adr.md", "---\ndescription: ADR\n---\n")

    records, sources = _catalog().discover_skills(project, claude_home=claude_home)
    project_records = {record.invocation: record for record in records if record.scope == "project"}

    assert project_records["/local"].kind == "skill"
    assert project_records["/adr"].kind == "command"
    assert {source.key for source in sources} >= {
        "user-skills",
        "user-commands",
        "project-skills",
        "project-commands",
    }


def test_every_searched_folder_is_reported_even_when_it_does_not_exist(claude_home: Path) -> None:
    _, sources = _catalog().discover_skills(None, claude_home=claude_home)
    commands = next(source for source in sources if source.key == "user-commands")

    assert commands.exists is False
    assert commands.count == 0


def test_plugin_skills_come_from_the_installed_manifest_and_use_the_manifest_name(
    claude_home: Path, tmp_path: Path
) -> None:
    install = tmp_path / "plugin-install"
    _write(install / ".claude-plugin" / "plugin.json", json.dumps({"name": "vendor"}))
    _write(install / "skills" / "deploy" / "SKILL.md", "---\nname: deploy\n---\n")
    _write(install / "commands" / "status.md", "---\ndescription: status\n---\n")
    _write(install / "commands" / "_conventions.md", "not a command\n")
    _write(
        claude_home / "plugins" / "installed_plugins.json",
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "vendor-plugin@market": [
                        {"scope": "user", "installPath": str(install), "version": "1.0.0"}
                    ]
                },
            }
        ),
    )

    records, sources = _catalog().discover_skills(None, claude_home=claude_home)
    plugin_records = [record for record in records if record.scope == "plugin"]

    assert {record.invocation for record in plugin_records} == {"/vendor:deploy", "/vendor:status"}
    assert all(record.plugin == "vendor" for record in plugin_records)
    plugin_source = next(source for source in sources if source.scope == "plugin")
    assert plugin_source.plugin_version == "1.0.0"


def test_a_plugin_switched_off_in_settings_is_listed_but_not_loaded(
    claude_home: Path, tmp_path: Path
) -> None:
    install = tmp_path / "off-plugin"
    _write(install / ".claude-plugin" / "plugin.json", json.dumps({"name": "vendor"}))
    _write(install / "skills" / "deploy" / "SKILL.md", "---\nname: deploy\n---\n")
    _write(
        claude_home / "plugins" / "installed_plugins.json",
        json.dumps(
            {"plugins": {"vendor@market": [{"scope": "user", "installPath": str(install)}]}}
        ),
    )
    _write(claude_home / "settings.json", json.dumps({"enabledPlugins": {"vendor@market": False}}))

    records, _ = _catalog().discover_skills(None, claude_home=claude_home)
    plugin_record = next(record for record in records if record.scope == "plugin")

    assert plugin_record.loaded is False
    assert plugin_record.plugin_enabled is False


def test_a_project_scoped_plugin_install_only_applies_to_that_project(
    claude_home: Path, tmp_path: Path
) -> None:
    install = tmp_path / "scoped-plugin"
    _write(install / ".claude-plugin" / "plugin.json", json.dumps({"name": "vendor"}))
    _write(install / "skills" / "deploy" / "SKILL.md", "---\nname: deploy\n---\n")
    project = tmp_path / "repo"
    project.mkdir()
    _write(
        claude_home / "plugins" / "installed_plugins.json",
        json.dumps(
            {
                "plugins": {
                    "vendor@market": [
                        {
                            "scope": "project",
                            "projectPath": str(project),
                            "installPath": str(install),
                        }
                    ]
                }
            }
        ),
    )

    without_project, _ = _catalog().discover_skills(None, claude_home=claude_home)
    with_project, _ = _catalog().discover_skills(project, claude_home=claude_home)

    assert [record for record in without_project if record.scope == "plugin"] == []
    assert len([record for record in with_project if record.scope == "plugin"]) == 1


# -- frontmatter ---------------------------------------------------------


def test_frontmatter_reads_inline_scalars_block_scalars_and_lists() -> None:
    parsed = _catalog().parse_frontmatter(
        "name: demo\n"
        "description: >\n"
        "  first line\n"
        "  second line\n"
        "disable-model-invocation: true\n"
        "tags: [a, b]\n"
        "paths:\n"
        "  - one\n"
        "  - two\n"
        "model: opus\n"
    )

    assert parsed["description"] == "first line second line"
    assert parsed["disable-model-invocation"] is True
    assert parsed["tags"] == ["a", "b"]
    assert parsed["paths"] == ["one", "two"]
    # The nested block must not swallow the key that follows it.
    assert parsed["model"] == "opus"


# -- structure -----------------------------------------------------------


def test_body_is_split_into_sections_with_code_and_table_blocks() -> None:
    _, body = _catalog().split_frontmatter(SKILL_BODY)
    preamble, sections = _structure().parse_blocks(body)

    assert preamble == []
    assert [(section["level"], section["title"]) for section in sections] == [
        (1, "Demo skill"),
        (2, "First rule"),
    ]
    kinds = [block["type"] for block in sections[1]["blocks"]]
    assert kinds == ["paragraph", "code", "table"]
    code_block = sections[1]["blocks"][1]
    assert code_block["language"] == "python"
    assert code_block["text"] == "value = 1"
    table = sections[1]["blocks"][2]
    assert table["header"] == ["Scope", "Wins"]
    assert table["rows"] == [["project", "yes"], ["user", "no"]]


def test_references_resolve_known_skills_agents_and_real_paths(tmp_path: Path) -> None:
    _write(tmp_path / "global" / "hooks" / "demo.py", "print(1)\n")
    _, body = _catalog().split_frontmatter(SKILL_BODY)

    references = _structure().extract_references(
        body,
        self_invocation="/demo",
        known_skills={"/git": "user:skill:git"},
        known_agents=["python-architect"],
        path_roots=[tmp_path],
    )

    assert references["skills"] == [{"label": "/git", "target_id": "user:skill:git", "resolved": True}]
    assert references["agents"] == [
        {"label": "@python-architect", "target_id": None, "resolved": True}
    ]
    assert [item["label"] for item in references["files"]] == ["global/hooks/demo.py"]


def test_a_python_decorator_is_not_mistaken_for_an_agent_reference() -> None:
    references = _structure().extract_references(
        "Use `@property` here, and hand off to @not-installed-agent.",
        self_invocation="/demo",
        known_skills={},
        known_agents=[],
        path_roots=[],
    )

    labels = [item["label"] for item in references["agents"]]
    assert labels == ["@not-installed-agent"]


def test_bundled_files_list_everything_beside_skill_md(claude_home: Path) -> None:
    entries = _structure().bundled_files(claude_home / "skills" / "demo")

    assert [(entry["rel_path"], entry["group"]) for entry in entries] == [
        ("references/notes.md", "references")
    ]
    assert entries[0]["previewable"] is True


# -- precedence, drift, payloads -----------------------------------------


def test_a_project_skill_shadows_the_personal_skill_of_the_same_name(
    claude_home: Path, tmp_path: Path
) -> None:
    project = tmp_path / "repo"
    _write(project / ".claude" / "skills" / "demo" / "SKILL.md", "---\nname: demo\n---\n")

    inventory = _service().build_skill_inventory(project, claude_home=claude_home)
    by_id = {skill["id"]: skill for skill in inventory["skills"]}

    assert by_id["project:skill:demo"]["precedence"] == "effective"
    assert by_id["user:skill:demo"]["precedence"] == "shadowed"
    assert by_id["user:skill:demo"]["duplicates"] == ["project:skill:demo"]
    assert inventory["counts"]["shadowed"] == 1


def test_the_inventory_lists_personal_skills_before_project_and_plugin_ones(
    claude_home: Path, tmp_path: Path
) -> None:
    project = tmp_path / "repo"
    _write(project / ".claude" / "skills" / "aaa-sorts-first" / "SKILL.md", "---\nname: aaa\n---\n")

    inventory = _service().build_skill_inventory(project, claude_home=claude_home)

    assert [skill["scope"] for skill in inventory["skills"]][0] == "user"


def test_two_definitions_in_the_same_scope_are_reported_as_ambiguous(
    claude_home: Path, tmp_path: Path
) -> None:
    project = tmp_path / "repo"
    _write(project / ".claude" / "skills" / "adr" / "SKILL.md", "---\nname: adr\n---\n")
    _write(project / ".claude" / "commands" / "adr.md", "---\ndescription: ADR\n---\n")

    inventory = _service().build_skill_inventory(project, claude_home=claude_home)
    states = {skill["id"]: skill["precedence"] for skill in inventory["skills"]}

    assert states["project:skill:adr"] == "ambiguous"
    assert states["project:command:adr"] == "ambiguous"


def test_drift_compares_the_applied_copy_with_this_repo_source_ignoring_line_endings(
    claude_home: Path, tmp_path: Path, monkeypatch
) -> None:
    service = _service()
    repo_global = tmp_path / "global"
    _write(repo_global / "skills" / "demo" / "SKILL.md", SKILL_BODY.replace("\n", "\r\n"))
    _write(repo_global / "skills" / "never-applied" / "SKILL.md", "---\nname: never\n---\n")
    monkeypatch.setattr(service, "GLOBAL_DIR", repo_global)

    inventory = service.build_skill_inventory(None, claude_home=claude_home)
    by_id = {skill["id"]: skill for skill in inventory["skills"]}

    assert by_id["user:skill:demo"]["drift"] == "in_sync"
    assert by_id["user:skill:loose"]["drift"] == "not_in_repo"
    assert inventory["unapplied_repo_skills"] == [
        {"name": "never-applied", "path": str(repo_global / "skills" / "never-applied" / "SKILL.md")}
    ]


def test_drift_flags_an_applied_copy_that_no_longer_matches_the_repo(
    claude_home: Path, tmp_path: Path, monkeypatch
) -> None:
    service = _service()
    repo_global = tmp_path / "global"
    _write(repo_global / "skills" / "demo" / "SKILL.md", SKILL_BODY + "\nEdited in the repo.\n")
    monkeypatch.setattr(service, "GLOBAL_DIR", repo_global)

    inventory = service.build_skill_inventory(None, claude_home=claude_home)
    demo = next(skill for skill in inventory["skills"] if skill["id"] == "user:skill:demo")

    assert demo["drift"] == "differs"
    assert inventory["counts"]["drifted"] == 1


def test_detail_carries_the_outline_frontmatter_bundles_and_references(claude_home: Path) -> None:
    detail = _service().build_skill_detail("user:skill:demo", None, claude_home=claude_home)

    assert detail["invocation"] == "/demo"
    assert detail["allowed_tools"] == ["Bash", "Read"]
    assert [section["title"] for section in detail["sections"]] == ["Demo skill", "First rule"]
    assert detail["bundled_files"][0]["rel_path"] == "references/notes.md"
    assert detail["references"]["agents"][0]["label"] == "@python-architect"
    assert detail["frontmatter_raw"].startswith("name: demo")


def test_detail_for_an_unknown_id_is_a_not_found_api_error(claude_home: Path) -> None:
    from cabal.webapi.envelope import ApiError

    with pytest.raises(ApiError) as excinfo:
        _service().build_skill_detail("user:skill:nope", None, claude_home=claude_home)
    assert excinfo.value.code == "not_found"


def test_a_bundled_asset_reads_only_from_inside_its_own_skill_folder(claude_home: Path) -> None:
    from cabal.webapi.envelope import ApiError

    service = _service()
    asset = service.read_skill_asset(
        "user:skill:demo", "references/notes.md", None, claude_home=claude_home
    )
    assert asset["content"] == "# notes\n"
    assert asset["binary"] is False

    with pytest.raises(ApiError) as excinfo:
        service.read_skill_asset(
            "user:skill:demo", "../../settings.json", None, claude_home=claude_home
        )
    assert excinfo.value.code == "path_outside_root"


# -- endpoints -----------------------------------------------------------


def test_skills_endpoint_envelopes_an_inventory(app_factory) -> None:
    _, client = build_client(app_factory)
    response = client.get("/api/agent-config/skills", headers=auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    data = payload["data"]
    assert {"counts", "sources", "skills", "claude_home"} <= set(data)
    assert {"total", "loaded", "not_loaded", "user", "project", "plugin"} <= set(data["counts"])


def test_skill_detail_endpoint_reports_an_unknown_id_as_not_found(app_factory) -> None:
    _, client = build_client(app_factory)
    response = client.get(
        "/api/agent-config/skills/detail",
        params={"skill_id": "user:skill:definitely-not-installed"},
        headers=auth_headers(),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
