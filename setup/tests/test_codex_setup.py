# -*- coding: utf-8 -*-
"""Tests for Codex setup helpers."""

from __future__ import annotations

import json

from cabal.codex_setup import components as codex_components
from cabal.codex_setup import conversion, diff_apply, local_setup
from cabal.codex_setup.components import CodexComponent


def _write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_codex_diff_and_apply_copies_changed_file(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    monkeypatch.setattr(codex_components, "CODEX_SOURCE_DIR", source)
    monkeypatch.setattr(codex_components, "CODEX_TARGET", target)
    monkeypatch.setattr(diff_apply, "CODEX_TARGET", target)

    _write(source / "skills" / "demo" / "SKILL.md", "new")
    _write(target / "skills" / "demo" / "SKILL.md", "old")
    comp = CodexComponent("skills", "skills/", "dir", "skills", "skills", recursive=True)

    statuses = diff_apply.diff_codex_component(comp)
    assert [status.state for status in statuses] == ["CHANGED"]

    copied, skipped = diff_apply.apply_codex_statuses(statuses)

    assert copied == 1
    assert skipped == 0
    assert (target / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8") == "new"


def test_codex_local_plan_and_apply_syncs_skill_folder(tmp_path, monkeypatch):
    source = tmp_path / "global" / "codex"
    project = tmp_path / "project"
    monkeypatch.setattr(local_setup, "CODEX_SOURCE_DIR", source)

    _write(source / "skills" / "demo" / "SKILL.md", "new")
    _write(project / ".agents" / "skills" / "demo" / "SKILL.md", "old")

    groups = local_setup.build_codex_local_plan(project, {"skills": True}, None)
    skills = next(group for group in groups if group["action"] == "skills")
    changed = next(child for child in skills["children"] if child["label"] == "demo")

    assert changed["op"] is not None
    assert "CHANGED" in changed["state"]

    local_setup.apply_codex_local_group("skills", [changed])

    assert (project / ".agents" / "skills" / "demo" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "new"


def test_codex_local_apply_ignores_noop_rows(tmp_path):
    noop = {
        "key": "template::none",
        "label": "AGENTS.md",
        "state": "[yellow]Pick a template above[/yellow]",
        "op": None,
    }

    assert local_setup.apply_codex_local_group("template", [noop]) == []


def test_codex_promptlib_component_targets_promptlib_subdir():
    comp = CodexComponent(
        "manifest",
        "prompt-lib/conversion-manifest.json",
        "file",
        "conversion-manifest.json",
        "prompt-lib/conversion-manifest.json",
    )

    assert comp.dst_path.name == "conversion-manifest.json"
    assert comp.dst_path.parent.name == "prompt-lib"


def test_conversion_manifest_audit_classifies_rows(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    codex = root / "global" / "codex"
    monkeypatch.setattr(conversion, "RESOURCE_ROOT", root)
    monkeypatch.setattr(conversion, "CODEX_SOURCE_DIR", codex)

    _write(root / "global" / "skills" / "demo.md", "source")
    _write(codex / "skills" / "demo" / "SKILL.md", "converted")
    manifest = {
        "version": 1,
        "entries": [
            {
                "source": "global/skills/demo.md",
                "output": "global/codex/skills/demo/SKILL.md",
                "kind": "skill",
                "status": "converted",
                "reason": "converted",
            },
            {
                "source": "global/hooks/",
                "output": None,
                "kind": "unsupported",
                "status": "unsupported",
                "reason": "hook runtime",
            },
            {
                "source": None,
                "output": "global/codex/README.md",
                "kind": "reference",
                "status": "codex-only",
                "reason": "doc",
            },
        ],
    }
    _write(codex / "README.md", "doc")
    _write(codex / "conversion-manifest.json", json.dumps(manifest))

    rows = conversion.audit_conversion_entries()

    assert [row.status for row in rows] == ["converted", "stale", "codex-only"]
    assert rows[0].source_label == "global/skills/demo.md"
    assert rows[0].output_label == "global/codex/skills/demo/SKILL.md"
