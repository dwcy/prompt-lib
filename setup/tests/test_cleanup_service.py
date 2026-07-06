# -*- coding: utf-8 -*-
"""Unit tests for cleanup_service: classification, backup-first removal, restore."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from cabal import cleanup_service
from cabal.cleanup_service import (
    CLEANUP_BACKUP_DIRNAME,
    MANIFEST_NAME,
    backup_and_remove,
    classify_extra,
    collect_extras,
    group_by_component,
    list_cleanup_backups,
    restore_cleanup,
)


@dataclass
class _StubComponent:
    key: str
    label: str
    type: str
    dst_path: Path


@pytest.fixture
def target(tmp_path) -> Path:
    t = tmp_path / "claude"
    (t / "skills").mkdir(parents=True)
    return t


def _make_file(path: Path, content: str = "content") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_classify_extra_flat_md_under_skills_is_stale():
    classification, reason = classify_extra("skills", Path("old-skill.md"))

    assert classification == "stale"
    assert "skills/*.md" in reason


def test_classify_extra_nested_skill_file_is_unknown():
    classification, _ = classify_extra("skills", Path("my-skill/SKILL.md"))

    assert classification == "unknown"


def test_classify_extra_flat_md_under_agents_is_unknown():
    classification, _ = classify_extra("agents", Path("my-agent.md"))

    assert classification == "unknown"


def test_classify_extra_non_md_flat_skills_file_is_unknown():
    classification, _ = classify_extra("skills", Path("notes.txt"))

    assert classification == "unknown"


def test_collect_extras_classifies_and_resolves_paths_per_component(
    tmp_path, monkeypatch
):
    comps = [
        _StubComponent("skills", "skills/", "dir", tmp_path / "skills"),
        _StubComponent("agents", "agents/", "dir", tmp_path / "agents"),
    ]
    rels = {
        "skills": [Path("dead.md"), Path("mine/SKILL.md")],
        "agents": [Path("custom.md")],
    }
    monkeypatch.setattr(cleanup_service, "COMPONENTS", comps)
    monkeypatch.setattr(
        cleanup_service, "find_extras", lambda comp: rels.get(comp.key, [])
    )

    extras = collect_extras()

    by_rel = {(e.component_key, e.rel.as_posix()): e for e in extras}
    assert set(by_rel) == {
        ("skills", "dead.md"),
        ("skills", "mine/SKILL.md"),
        ("agents", "custom.md"),
    }
    assert by_rel[("skills", "dead.md")].classification == "stale"
    assert by_rel[("skills", "mine/SKILL.md")].classification == "unknown"
    assert by_rel[("agents", "custom.md")].classification == "unknown"
    assert by_rel[("skills", "dead.md")].path == tmp_path / "skills" / "dead.md"


def test_collect_extras_skips_file_components(tmp_path, monkeypatch):
    comps = [
        _StubComponent("settings", "settings.json", "file", tmp_path / "settings.json")
    ]
    monkeypatch.setattr(cleanup_service, "COMPONENTS", comps)
    monkeypatch.setattr(
        cleanup_service,
        "find_extras",
        lambda comp: pytest.fail("file components must never be scanned"),
    )

    assert collect_extras() == []


def test_group_by_component_preserves_components_order_and_sorts_rels(
    tmp_path, monkeypatch
):
    comps = [
        _StubComponent("agents", "agents/", "dir", tmp_path / "agents"),
        _StubComponent("skills", "skills/", "dir", tmp_path / "skills"),
    ]
    rels = {
        "skills": [Path("zzz.md"), Path("aaa.md")],
        "agents": [Path("bot.md")],
    }
    monkeypatch.setattr(cleanup_service, "COMPONENTS", comps)
    monkeypatch.setattr(
        cleanup_service, "find_extras", lambda comp: rels.get(comp.key, [])
    )
    extras = collect_extras()

    grouped = group_by_component(extras)

    assert [label for label, _ in grouped] == ["agents/", "skills/"]
    skills = dict(grouped)["skills/"]
    assert [e.rel.as_posix() for e in skills] == ["aaa.md", "zzz.md"]


def test_backup_and_remove_backs_up_verifies_then_deletes(target):
    original = _make_file(target / "skills" / "dead.md", "skill body")

    result = backup_and_remove([original], target=target)

    assert result.backed_up == [original]
    assert result.deleted == [original]
    assert result.errors == {}
    assert not original.exists()
    backup_copy = result.backup_dir / "skills" / "dead.md"
    assert backup_copy.read_text(encoding="utf-8") == "skill body"


def test_backup_and_remove_preserves_relative_paths_in_backup(target):
    nested = _make_file(target / "skills" / "old" / "SKILL.md", "nested")

    result = backup_and_remove([nested], target=target)

    assert (result.backup_dir / "skills" / "old" / "SKILL.md").is_file()


def test_backup_and_remove_writes_manifest_with_entries(target):
    original = _make_file(target / "skills" / "dead.md", "12345")

    result = backup_and_remove([original], target=target)

    manifest = json.loads(
        (result.backup_dir / MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert manifest["target"] == str(target)
    assert manifest["entries"] == [{"relative_path": "skills/dead.md", "size": 5}]
    assert manifest["timestamp"] == result.backup_dir.name


def test_backup_and_remove_manifest_exists_before_any_delete(target, monkeypatch):
    original = _make_file(target / "skills" / "dead.md")
    manifest_present_at_unlink: list[bool] = []
    real_unlink = Path.unlink

    def spy(self: Path, *args, **kwargs):
        manifests = list((target / CLEANUP_BACKUP_DIRNAME).glob(f"*/{MANIFEST_NAME}"))
        manifest_present_at_unlink.append(bool(manifests))
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", spy)

    backup_and_remove([original], target=target)

    assert manifest_present_at_unlink == [True]


def test_backup_and_remove_refuses_path_outside_target(tmp_path, target):
    outside = _make_file(tmp_path / "elsewhere" / "keep.md", "precious")

    result = backup_and_remove([outside], target=target)

    assert outside.read_text(encoding="utf-8") == "precious"
    assert result.deleted == []
    assert "outside" in result.errors[outside]
    assert not (target / CLEANUP_BACKUP_DIRNAME).exists()


def test_backup_and_remove_reports_missing_file(target):
    ghost = target / "skills" / "ghost.md"

    result = backup_and_remove([ghost], target=target)

    assert result.deleted == []
    assert ghost in result.errors
    assert not (target / CLEANUP_BACKUP_DIRNAME).exists()


def test_backup_and_remove_failed_verification_keeps_original(target, monkeypatch):
    original = _make_file(target / "skills" / "dead.md", "keep me")
    monkeypatch.setattr(cleanup_service.filecmp, "cmp", lambda *a, **k: False)

    result = backup_and_remove([original], target=target)

    assert original.read_text(encoding="utf-8") == "keep me"
    assert result.deleted == []
    assert "verification failed" in result.errors[original]
    assert not (target / CLEANUP_BACKUP_DIRNAME).exists()


def test_backup_and_remove_empty_selection_is_a_noop(target):
    result = backup_and_remove([], target=target)

    assert result.backup_dir is None
    assert result.backed_up == []
    assert not (target / CLEANUP_BACKUP_DIRNAME).exists()


def test_backup_and_remove_touches_only_listed_files(target):
    chosen = _make_file(target / "skills" / "dead.md")
    sibling = _make_file(target / "skills" / "alive.md", "still here")

    result = backup_and_remove([chosen], target=target)

    assert result.deleted == [chosen]
    assert sibling.read_text(encoding="utf-8") == "still here"
    assert not (result.backup_dir / "skills" / "alive.md").exists()


def test_backup_and_remove_mixes_valid_and_refused_paths(tmp_path, target):
    valid = _make_file(target / "skills" / "dead.md")
    outside = _make_file(tmp_path / "outside.md")

    result = backup_and_remove([valid, outside], target=target)

    assert result.deleted == [valid]
    assert outside.exists()
    assert set(result.errors) == {outside}


def test_restore_cleanup_restores_files_and_recreates_dirs(target):
    original = _make_file(target / "skills" / "old" / "SKILL.md", "nested body")
    backup_dir = backup_and_remove([original], target=target).backup_dir
    (target / "skills" / "old").rmdir()

    result = restore_cleanup(backup_dir, target=target)

    assert result.restored == [original]
    assert result.skipped == [] and result.errors == {}
    assert original.read_text(encoding="utf-8") == "nested body"


def test_restore_cleanup_skips_destination_newer_on_disk(target):
    original = _make_file(target / "skills" / "dead.md", "old body")
    backup_dir = backup_and_remove([original], target=target).backup_dir
    _make_file(original, "newer body")
    backup_mtime = (backup_dir / "skills" / "dead.md").stat().st_mtime
    os.utime(original, (backup_mtime + 100, backup_mtime + 100))

    result = restore_cleanup(backup_dir, target=target)

    assert result.restored == []
    assert [path for path, _ in result.skipped] == [original]
    assert original.read_text(encoding="utf-8") == "newer body"


def test_restore_cleanup_overwrites_destination_older_than_backup(target):
    original = _make_file(target / "skills" / "dead.md", "backed up")
    backup_dir = backup_and_remove([original], target=target).backup_dir
    _make_file(original, "stale rewrite")
    backup_mtime = (backup_dir / "skills" / "dead.md").stat().st_mtime
    os.utime(original, (backup_mtime - 100, backup_mtime - 100))

    result = restore_cleanup(backup_dir, target=target)

    assert result.restored == [original]
    assert original.read_text(encoding="utf-8") == "backed up"


def test_restore_cleanup_missing_manifest_reports_error(target):
    bogus = target / CLEANUP_BACKUP_DIRNAME / "20260101-000000"
    bogus.mkdir(parents=True)

    result = restore_cleanup(bogus, target=target)

    assert result.restored == []
    assert bogus / MANIFEST_NAME in result.errors


def test_restore_cleanup_missing_backup_file_reports_error(target):
    original = _make_file(target / "skills" / "dead.md")
    backup_dir = backup_and_remove([original], target=target).backup_dir
    (backup_dir / "skills" / "dead.md").unlink()

    result = restore_cleanup(backup_dir, target=target)

    assert result.restored == []
    assert result.errors == {original: "Missing from backup"}


def _write_manifest(root: Path, ts: str, sizes: list[int]) -> Path:
    sub = root / CLEANUP_BACKUP_DIRNAME / ts
    sub.mkdir(parents=True)
    entries = [
        {"relative_path": f"skills/f{i}.md", "size": s} for i, s in enumerate(sizes)
    ]
    (sub / MANIFEST_NAME).write_text(
        json.dumps({"timestamp": ts, "target": str(root), "entries": entries}),
        encoding="utf-8",
    )
    return sub


def test_list_cleanup_backups_empty_when_no_backup_dir(target):
    assert list_cleanup_backups(target=target) == []


def test_list_cleanup_backups_summarises_each_manifest(target):
    _write_manifest(target, "20260101-000000", [10, 20])

    infos = list_cleanup_backups(target=target)

    assert len(infos) == 1
    assert infos[0].timestamp == "20260101-000000"
    assert infos[0].entry_count == 2
    assert infos[0].total_bytes == 30


def test_list_cleanup_backups_orders_newest_first(target):
    _write_manifest(target, "20260101-000000", [1])
    _write_manifest(target, "20260202-000000", [1])

    infos = list_cleanup_backups(target=target)

    assert [b.timestamp for b in infos] == ["20260202-000000", "20260101-000000"]


def test_list_cleanup_backups_ignores_dirs_without_valid_manifest(target):
    _write_manifest(target, "20260101-000000", [1])
    (target / CLEANUP_BACKUP_DIRNAME / "no-manifest").mkdir()
    corrupt = target / CLEANUP_BACKUP_DIRNAME / "20260303-000000"
    corrupt.mkdir()
    (corrupt / MANIFEST_NAME).write_text("{not json", encoding="utf-8")

    infos = list_cleanup_backups(target=target)

    assert [b.timestamp for b in infos] == ["20260101-000000"]
