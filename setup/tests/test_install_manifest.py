# -*- coding: utf-8 -*-
"""Tests for cabal.install_manifest — persistence, journaling, and traversal guards."""

from __future__ import annotations

import json

import pytest

from cabal import _paths, install_manifest
from cabal.install_manifest import (
    HISTORY_KEEP,
    InstallManifest,
    ManagedFile,
    ManifestError,
)


@pytest.fixture
def tmp_target(tmp_path, monkeypatch):
    """Isolate cabal._paths.TARGET so manifest reads/writes land under tmp_path."""
    target = tmp_path / ".claude"
    monkeypatch.setattr(_paths, "TARGET", target, raising=True)
    return target


def _sample_manifest(
    applied_at: str = "2026-01-01T00:00:00+00:00", status: str = "complete"
) -> InstallManifest:
    files = [
        ManagedFile(
            component="agents", rel="foo.md", sha256="a" * 64, action="created"
        ),
        ManagedFile(
            component="hooks",
            rel="bar.py",
            sha256="b" * 64,
            action="updated",
            backup="backup/bar.py",
        ),
        ManagedFile(
            component="skills", rel="baz.md", sha256="c" * 64, action="unchanged"
        ),
    ]
    return InstallManifest(
        tool_version="1.2.3",
        source_mode="source",
        applied_at=applied_at,
        status=status,
        components=["agents", "hooks", "skills"],
        backup_dir=None,
        files=files,
    )


def _valid_manifest_dict(files=None, schema_version: int = 1) -> dict:
    return {
        "schema_version": schema_version,
        "tool_version": "1.2.3",
        "source_mode": "source",
        "applied_at": "2026-01-01T00:00:00+00:00",
        "status": "complete",
        "components": ["agents"],
        "backup_dir": None,
        "files": files if files is not None else [],
    }


def _write_manifest_json(target, data: dict) -> None:
    path = install_manifest.manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class TestSaveLoadRoundtrip:
    def test_load_returns_equal_manifest_after_save(self, tmp_target):
        manifest = _sample_manifest()

        install_manifest.save_manifest(manifest)
        loaded = install_manifest.load_manifest()

        assert loaded == manifest

    def test_load_preserves_each_action_and_backup_field(self, tmp_target):
        manifest = _sample_manifest()

        install_manifest.save_manifest(manifest)
        loaded = install_manifest.load_manifest()

        by_rel = {f.rel: f for f in loaded.files}
        assert by_rel["foo.md"].action == "created"
        assert by_rel["foo.md"].backup is None
        assert by_rel["bar.py"].action == "updated"
        assert by_rel["bar.py"].backup == "backup/bar.py"
        assert by_rel["baz.md"].action == "unchanged"


class TestJournalTransitions:
    def test_begin_apply_writes_in_progress_and_is_detected(self, tmp_target):
        manifest = _sample_manifest(status="complete")

        install_manifest.begin_apply(manifest)

        interrupted = install_manifest.detect_interrupted()
        assert interrupted is not None
        assert interrupted.status == "in_progress"

    def test_complete_apply_clears_interrupted_detection(self, tmp_target):
        manifest = _sample_manifest(status="complete")
        install_manifest.begin_apply(manifest)

        install_manifest.complete_apply(manifest)

        assert install_manifest.detect_interrupted() is None
        assert install_manifest.load_manifest().status == "complete"


class TestLoadManifestFailureModes:
    def test_missing_file_returns_none(self, tmp_target):
        assert install_manifest.load_manifest() is None

    def test_invalid_json_returns_none(self, tmp_target):
        path = install_manifest.manifest_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ not valid json", encoding="utf-8")

        assert install_manifest.load_manifest() is None

    def test_unknown_schema_version_returns_none(self, tmp_target):
        _write_manifest_json(tmp_target, _valid_manifest_dict(schema_version=99))

        assert install_manifest.load_manifest() is None


class TestTraversalGuard:
    @pytest.mark.parametrize(
        "bad_rel",
        [
            "../evil",
            "/etc/passwd",
            "C:\\x",
        ],
    )
    def test_unsafe_rel_raises_manifest_error(self, tmp_target, bad_rel):
        entry = {
            "component": "agents",
            "rel": bad_rel,
            "sha256": "a" * 64,
            "action": "created",
        }
        _write_manifest_json(tmp_target, _valid_manifest_dict(files=[entry]))

        with pytest.raises(ManifestError):
            install_manifest.load_manifest()


class TestHistoryRotation:
    def _run_cycle(self, day: int) -> None:
        applied_at = f"2026-02-{day:02d}T00:00:00+00:00"
        manifest = _sample_manifest(applied_at=applied_at, status="in_progress")
        install_manifest.begin_apply(manifest)
        install_manifest.complete_apply(manifest)

    def test_more_than_keep_cycles_prunes_history_to_cap(self, tmp_target):
        total_cycles = HISTORY_KEEP + 2

        for day in range(1, total_cycles + 1):
            self._run_cycle(day)

        snapshots = list(install_manifest.history_dir().glob("*.json"))
        assert len(snapshots) == HISTORY_KEEP

    def test_oldest_snapshot_is_pruned_not_newest(self, tmp_target):
        total_cycles = HISTORY_KEEP + 2

        for day in range(1, total_cycles + 1):
            self._run_cycle(day)

        applied_ats = set()
        for snapshot in install_manifest.history_dir().glob("*.json"):
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            applied_ats.add(data["applied_at"])

        oldest = "2026-02-01T00:00:00+00:00"
        newest_rotated = f"2026-02-{total_cycles - 1:02d}T00:00:00+00:00"
        assert oldest not in applied_ats
        assert newest_rotated in applied_ats

    def test_in_progress_previous_manifest_is_not_rotated(self, tmp_target):
        first = _sample_manifest(applied_at="2026-03-01T00:00:00+00:00")
        install_manifest.begin_apply(first)  # left in_progress, never completed

        second = _sample_manifest(applied_at="2026-03-02T00:00:00+00:00")
        install_manifest.begin_apply(second)

        history = install_manifest.history_dir()
        snapshots = list(history.glob("*.json")) if history.is_dir() else []
        assert snapshots == []
        assert install_manifest.load_manifest().applied_at == "2026-03-02T00:00:00+00:00"


class TestCurrentSourceMode:
    def test_frozen_takes_priority_over_installed(self, monkeypatch):
        monkeypatch.setattr(_paths, "IS_FROZEN", True, raising=True)
        monkeypatch.setattr(_paths, "IS_INSTALLED", True, raising=True)

        assert install_manifest.current_source_mode() == "frozen"

    def test_installed_wheel_when_not_frozen(self, monkeypatch):
        monkeypatch.setattr(_paths, "IS_FROZEN", False, raising=True)
        monkeypatch.setattr(_paths, "IS_INSTALLED", True, raising=True)

        assert install_manifest.current_source_mode() == "wheel"

    def test_source_when_neither_frozen_nor_installed(self, monkeypatch):
        monkeypatch.setattr(_paths, "IS_FROZEN", False, raising=True)
        monkeypatch.setattr(_paths, "IS_INSTALLED", False, raising=True)

        assert install_manifest.current_source_mode() == "source"
