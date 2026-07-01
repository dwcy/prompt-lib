"""Unit tests for the model-assignments service (collect + set_model rewrite)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cabal.model_assignments import (
    ModelAssignment,
    collect_model_assignments,
    set_model,
)


def _write(path: Path, frontmatter: str, body: str = "Body.\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")


@pytest.fixture()
def global_dir(tmp_path: Path) -> Path:
    root = tmp_path / "global"
    _write(root / "agents" / "pinned.md", "name: pinned\nmodel: opus\n")
    _write(root / "agents" / "plain.md", "name: plain\n")
    _write(root / "skills" / "flat.md", "name: flat\nmodel: bogus-model\n")
    _write(root / "skills" / "dirstyle" / "SKILL.md", "name: dirstyle\nmodel: haiku\n")
    return root


def test_collect_reports_pin_inherit_and_invalid(global_dir: Path) -> None:
    rows = {(r.kind, r.name): r for r in collect_model_assignments(global_dir)}

    assert rows[("agent", "pinned")] == ModelAssignment("agent", "pinned", "opus", True)
    assert rows[("agent", "plain")].model == "inherit"
    assert rows[("agent", "plain")].valid is True
    assert rows[("skill", "dirstyle")].model == "haiku"
    assert rows[("skill", "flat")].valid is False


def test_set_model_inserts_a_missing_pin(global_dir: Path, tmp_path: Path) -> None:
    written = set_model("agent", "plain", "sonnet", global_dir, tmp_path / "empty")

    text = (global_dir / "agents" / "plain.md").read_text(encoding="utf-8")
    assert "model: sonnet" in text.split("---")[1]
    assert written == [global_dir / "agents" / "plain.md"]


def test_set_model_replaces_an_existing_pin(global_dir: Path, tmp_path: Path) -> None:
    set_model("agent", "pinned", "fable", global_dir, tmp_path / "empty")

    frontmatter = (
        (global_dir / "agents" / "pinned.md")
        .read_text(encoding="utf-8")
        .split("---")[1]
    )
    assert "model: fable" in frontmatter
    assert "model: opus" not in frontmatter


def test_set_model_inherit_removes_the_pin_and_keeps_body(
    global_dir: Path, tmp_path: Path
) -> None:
    set_model("skill", "dirstyle", "inherit", global_dir, tmp_path / "empty")

    text = (global_dir / "skills" / "dirstyle" / "SKILL.md").read_text(encoding="utf-8")
    assert "model:" not in text
    assert text.rstrip().endswith("Body.")


def test_set_model_mirrors_into_deployed_copy(global_dir: Path, tmp_path: Path) -> None:
    target = tmp_path / "dot-claude"
    _write(target / "agents" / "pinned.md", "name: pinned\nmodel: opus\n")

    written = set_model("agent", "pinned", "haiku", global_dir, target)

    deployed = (target / "agents" / "pinned.md").read_text(encoding="utf-8")
    assert "model: haiku" in deployed
    assert len(written) == 2


def test_set_model_rejects_unknown_values_and_names(
    global_dir: Path, tmp_path: Path
) -> None:
    with pytest.raises(ValueError):
        set_model("agent", "pinned", "gpt-5", global_dir, tmp_path)
    with pytest.raises(ValueError):
        set_model("agent", "missing", "opus", global_dir, tmp_path)
