# -*- coding: utf-8 -*-
"""Unit tests for cabal.config_doctor — each check exercised against a tmp ~/.claude tree."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal import widget_cache
from cabal.config_doctor import run_doctor, run_doctor_cached, tree_fingerprint


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the shared widget cache into tmp_path so tests never touch ~/.cabal."""
    cache_dir = tmp_path / "cabal-cache"
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", cache_dir)
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", cache_dir / "cache.json")
    return cache_dir


def _healthy_tree(root: Path) -> Path:
    skills = root / "skills" / "good-skill"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\nname: good-skill\ndescription: Does a thing. Use when asked.\n---\n\nBody.\n",
        encoding="utf-8",
    )
    agents = root / "agents"
    agents.mkdir()
    (agents / "helper.md").write_text(
        "---\nname: helper\ndescription: Helps with things.\n---\n\nPrompt.\n",
        encoding="utf-8",
    )
    hooks = root / "hooks"
    hooks.mkdir()
    (hooks / "guard.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "settings.json").write_text(
        json.dumps({
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Task|Agent",
                        "hooks": [{"type": "command", "command": 'python "$USERPROFILE/.claude/hooks/guard.py"'}],
                    }
                ]
            }
        }),
        encoding="utf-8",
    )
    (root / "CLAUDE.md").write_text(
        "Use `/good-skill` for things and `/doctor` for health.\n", encoding="utf-8"
    )
    return root


def test_healthy_tree_yields_no_findings(tmp_path: Path):
    root = _healthy_tree(tmp_path)

    findings = run_doctor(root)

    assert findings == []


def test_flat_md_under_skills_is_a_dead_skill_error(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    (root / "skills" / "orphan.md").write_text("---\nname: orphan\n---\n", encoding="utf-8")

    findings = run_doctor(root)

    assert [(f.severity, f.category) for f in findings] == [("error", "dead-flat-skill")]


def test_skill_dir_without_skill_md_is_an_error(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    (root / "skills" / "hollow").mkdir()

    findings = run_doctor(root)

    assert [(f.severity, f.category) for f in findings] == [("error", "missing-skill-md")]


def test_bom_in_skill_md_is_an_error(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    bommed = root / "skills" / "bommed"
    bommed.mkdir()
    (bommed / "SKILL.md").write_bytes(
        b"\xef\xbb\xbf---\nname: bommed\ndescription: Fine otherwise.\n---\n"
    )

    findings = run_doctor(root)

    assert [(f.severity, f.category) for f in findings] == [("error", "bom")]


def test_missing_description_is_a_warning(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    quiet = root / "skills" / "quiet"
    quiet.mkdir()
    (quiet / "SKILL.md").write_text("---\nname: quiet\n---\n\nBody.\n", encoding="utf-8")

    findings = run_doctor(root)

    assert [(f.severity, f.category) for f in findings] == [("warning", "no-description")]


def test_description_over_listing_cap_is_a_warning(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    wordy = root / "skills" / "wordy"
    wordy.mkdir()
    (wordy / "SKILL.md").write_text(
        f"---\nname: wordy\ndescription: {'x' * 1600}\n---\n", encoding="utf-8"
    )

    findings = run_doctor(root)

    assert [(f.severity, f.category) for f in findings] == [("warning", "description-too-long")]


def test_agent_without_description_is_an_error(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    (root / "agents" / "nameless.md").write_text("---\nname: nameless\n---\n", encoding="utf-8")

    findings = run_doctor(root)

    assert [(f.severity, f.category) for f in findings] == [("error", "agent-frontmatter")]


def test_legacy_only_matcher_is_an_error(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    settings["hooks"]["PreToolUse"][0]["matcher"] = "Task"
    (root / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    findings = run_doctor(root)

    assert [(f.severity, f.category) for f in findings] == [("error", "legacy-matcher")]


def test_unknown_matcher_tool_is_a_warning(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    settings["hooks"]["PreToolUse"][0]["matcher"] = "Bash|Frobnicate"
    (root / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    findings = run_doctor(root)

    assert [(f.severity, f.category) for f in findings] == [("warning", "unknown-matcher-tool")]


def test_missing_hook_script_is_an_error(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    (root / "hooks" / "guard.py").unlink()

    findings = run_doctor(root)

    assert [(f.severity, f.category) for f in findings] == [("error", "hook-script-missing")]


def test_claude_md_reference_to_missing_skill_is_a_warning(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    (root / "CLAUDE.md").write_text("Repair with `/gone-skill` first.\n", encoding="utf-8")

    findings = run_doctor(root)

    assert [(f.severity, f.category) for f in findings] == [("warning", "dead-skill-reference")]


def test_claude_md_reference_resolved_by_project_scope_is_not_a_finding(tmp_path: Path):
    root = _healthy_tree(tmp_path / "home")
    (root / "CLAUDE.md").write_text("Use `/project-only` when planning.\n", encoding="utf-8")
    project = tmp_path / "repo"
    (project / ".claude" / "skills" / "project-only").mkdir(parents=True)

    findings = run_doctor(root, project=project)

    assert findings == []


def test_foreign_user_path_in_skill_is_a_warning(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    (root / "skills" / "good-skill" / "SKILL.md").write_text(
        "---\nname: good-skill\ndescription: Does a thing. Use when asked.\n---\n\n"
        "Run C:\\Users\\SomeoneElse\\.claude\\scripts\\x.py\n",
        encoding="utf-8",
    )

    findings = run_doctor(root)

    assert [(f.severity, f.category) for f in findings] == [("warning", "foreign-user-path")]


def test_errors_sort_before_warnings(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    (root / "skills" / "orphan.md").write_text("dead\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("`/gone-skill`\n", encoding="utf-8")

    findings = run_doctor(root)

    assert [f.severity for f in findings] == ["error", "warning"]


def test_unchanged_tree_reuses_cached_findings(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    (root / "skills" / "orphan.md").write_text("dead\n", encoding="utf-8")
    first, first_cached = run_doctor_cached(root)

    second, second_cached = run_doctor_cached(root)

    assert (first_cached, second_cached, second) == (False, True, first)


def test_changed_file_invalidates_the_cache(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    run_doctor_cached(root)
    (root / "skills" / "orphan.md").write_text("newly dead\n", encoding="utf-8")

    findings, from_cache = run_doctor_cached(root)

    assert (from_cache, [f.category for f in findings]) == (False, ["dead-flat-skill"])


def test_garbage_cache_entry_falls_through_to_a_fresh_scan(tmp_path: Path):
    root = _healthy_tree(tmp_path)
    widget_cache.save_entry(
        f"doctor:{root}",
        {"fingerprint": tree_fingerprint(root), "findings": [{"bogus": 1}]},
    )

    findings, from_cache = run_doctor_cached(root)

    assert (from_cache, findings) == (False, [])
