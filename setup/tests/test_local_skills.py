# -*- coding: utf-8 -*-
"""Tests for local project status + global→local skills drift/sync (plan items 3 & 4)."""

from __future__ import annotations

import pytest
from textual.widgets import Checkbox, Static

from cabal import local_setup
from cabal.app import CabalApp
from cabal.views.local import LocalScreen


def _write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _skills_children(project):
    groups = local_setup.build_plan(project, {"skills": True}, None, None)
    skills = next(g for g in groups if g["action"] == "skills")
    return {c["label"]: c for c in skills["children"]}


def test_project_status_reflects_present_and_absent(tmp_path):
    before = dict(local_setup.project_status(tmp_path))

    _write(tmp_path / "CLAUDE.md")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    after = dict(local_setup.project_status(tmp_path))

    assert before["CLAUDE.md"] is False
    assert after["CLAUDE.md"] is True
    assert after["skills/"] is True


def test_new_skill_is_selectable(tmp_path, monkeypatch):
    _write(tmp_path / "global" / "skills" / "fresh.md", "alpha")
    monkeypatch.setattr(local_setup, "GLOBAL_DIR", tmp_path / "global")

    children = _skills_children(tmp_path / "proj")

    assert children["fresh"]["op"] is not None
    assert "NEW" in children["fresh"]["state"]


def test_unchanged_skill_is_informational(tmp_path, monkeypatch):
    _write(tmp_path / "global" / "skills" / "same.md", "identical")
    monkeypatch.setattr(local_setup, "GLOBAL_DIR", tmp_path / "global")
    _write(tmp_path / "proj" / ".claude" / "skills" / "same.md", "identical")

    children = _skills_children(tmp_path / "proj")

    assert children["same"]["op"] is None
    assert "installed" in children["same"]["state"]


def test_changed_skill_is_selectable_and_marked(tmp_path, monkeypatch):
    _write(tmp_path / "global" / "skills" / "drift.md", "v2")
    monkeypatch.setattr(local_setup, "GLOBAL_DIR", tmp_path / "global")
    _write(tmp_path / "proj" / ".claude" / "skills" / "drift.md", "v1")

    children = _skills_children(tmp_path / "proj")

    assert children["drift"]["op"] is not None
    assert "CHANGED" in children["drift"]["state"]


def test_local_only_skill_is_kept_and_not_selectable(tmp_path, monkeypatch):
    _write(tmp_path / "global" / "skills" / "g.md", "g")
    monkeypatch.setattr(local_setup, "GLOBAL_DIR", tmp_path / "global")
    _write(tmp_path / "proj" / ".claude" / "skills" / "mine.md", "local")

    children = _skills_children(tmp_path / "proj")

    assert children["mine"]["op"] is None
    assert "local-only" in children["mine"]["state"]


def test_apply_skills_copies_selected_into_project(tmp_path, monkeypatch):
    _write(tmp_path / "global" / "skills" / "fresh.md", "alpha")
    monkeypatch.setattr(local_setup, "GLOBAL_DIR", tmp_path / "global")
    project = tmp_path / "proj"
    chosen = [c for c in _skills_children(project).values() if c["op"]]

    local_setup.apply_group("skills", chosen, project)

    assert (project / ".claude" / "skills" / "fresh.md").read_text(
        encoding="utf-8"
    ) == "alpha"


def _children(project, sel, tpl=None, picked=None, action=None):
    groups = local_setup.build_plan(project, sel, tpl, picked)
    grp = next(g for g in groups if g["action"] == action)
    return {c["label"]: c for c in grp["children"]}


def test_template_row_new_is_selectable(tmp_path):
    tpl = tmp_path / "python.md"
    _write(tpl, "template body")

    children = _children(
        tmp_path / "proj", {"template": True}, tpl, tpl, action="template"
    )
    row = next(iter(children.values()))

    assert row["op"] is not None
    assert "NEW" in row["state"]


def test_template_row_unchanged_is_informational(tmp_path):
    tpl = tmp_path / "python.md"
    _write(tpl, "identical body")
    _write(tmp_path / "proj" / "CLAUDE.md", "identical body")

    children = _children(
        tmp_path / "proj", {"template": True}, tpl, tpl, action="template"
    )
    row = next(iter(children.values()))

    assert row["op"] is None
    assert "installed" in row["state"]


def test_git_template_changed_is_selectable_and_marked(tmp_path, monkeypatch):
    _write(tmp_path / "global" / "git" / ".editorconfig", "v2")
    monkeypatch.setattr(local_setup, "GLOBAL_DIR", tmp_path / "global")
    _write(tmp_path / "proj" / ".editorconfig", "v1")

    children = _children(tmp_path / "proj", {"git": True}, action="git")

    assert children[".editorconfig"]["op"] is not None
    assert "CHANGED" in children[".editorconfig"]["state"]


@pytest.mark.asyncio
async def test_local_screen_mounts_with_status_and_skills_toggle():
    app = CabalApp()

    async with app.run_test() as pilot:
        screen = LocalScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#loc-skills", Checkbox) is not None
        assert screen.query_one("#loc-proj-status", Static) is not None
