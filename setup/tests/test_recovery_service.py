# -*- coding: utf-8 -*-
"""Tests for cabal.recovery_service — interrupted detection, resume, rollback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

import cabal
from cabal import _paths as cabal_paths
from cabal import components as cabal_components
from cabal import install_manifest
from cabal import recovery_service
from cabal import settings_helpers as cabal_settings_helpers
from cabal.apply_service import PlannedFile, apply_components, build_plan
from cabal.diff_apply import apply_statuses
from cabal.install_manifest import InstallManifest, ManagedFile

_STATE_TO_ACTION = {"NEW": "created", "CHANGED": "updated", "UNCHANGED": "unchanged"}


@dataclass
class Sandbox:
    source: Path
    target: Path


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Sandbox:
    """Isolated `global/` source payload + `~/.claude/` deploy target.

    Mirrors the seam-patching approach in test_headless_cli.py's Sandbox
    fixture: every module that binds GLOBAL_DIR/TARGET as a module-level name
    at import time must be patched individually.
    """
    source = tmp_path / "global_src"
    target = tmp_path / ".claude"
    (source / "agents").mkdir(parents=True)
    (source / "hooks").mkdir(parents=True)

    monkeypatch.setattr(cabal_paths, "TARGET", target, raising=True)
    monkeypatch.setattr(cabal_paths, "GLOBAL_DIR", source, raising=True)
    monkeypatch.setattr(cabal_components, "GLOBAL_DIR", source, raising=True)
    monkeypatch.setattr(cabal_components, "TARGET", target, raising=True)
    monkeypatch.setattr(cabal_settings_helpers, "GLOBAL_DIR", source, raising=True)

    return Sandbox(source=source, target=target)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _manual_entries(plan: list[PlannedFile]) -> list[ManagedFile]:
    """Manifest entries hashed from source — what begin_apply journals pre-write."""
    return [
        ManagedFile(
            component=pf.component,
            rel=Path(pf.status.rel).as_posix(),
            sha256=install_manifest.sha256_file(pf.status.src),
            action=_STATE_TO_ACTION[pf.status.state],
            backup=None,
        )
        for pf in plan
    ]


def _begin_interrupted(keys: list[str]) -> list[PlannedFile]:
    """Journal an in_progress manifest for `keys` without writing or completing it."""
    plan = build_plan(keys)
    manifest = InstallManifest(
        tool_version=cabal.__version__,
        source_mode=install_manifest.current_source_mode(),
        applied_at=datetime.now(UTC).isoformat(),
        status="in_progress",
        components=list(dict.fromkeys(pf.component for pf in plan)),
        backup_dir=None,
        files=_manual_entries(plan),
    )
    install_manifest.begin_apply(manifest)
    return plan


class TestInterruptedDetection:
    def test_returns_none_when_no_manifest_exists(self, sandbox):
        assert recovery_service.interrupted_state() is None

    def test_returns_none_when_last_apply_completed(self, sandbox):
        _write(sandbox.source / "agents" / "one.md", "# one\n")

        apply_components(["agents"])

        assert recovery_service.interrupted_state() is None

    def test_detects_manifest_left_in_progress_after_partial_write(self, sandbox):
        _write(sandbox.source / "agents" / "one.md", "# one\n")
        _write(sandbox.source / "agents" / "two.md", "# two\n")
        plan = _begin_interrupted(["agents"])
        [one_pf] = [pf for pf in plan if Path(pf.status.rel).as_posix() == "one.md"]
        apply_statuses([one_pf.status])  # only one.md written before the crash

        interrupted = recovery_service.interrupted_state()

        assert interrupted is not None
        assert interrupted.status == "in_progress"
        assert interrupted.components == ["agents"]
        assert {f.rel for f in interrupted.files} == {"one.md", "two.md"}


class TestResume:
    def test_resume_completes_deploy_and_flips_status_to_complete(self, sandbox):
        _write(sandbox.source / "agents" / "one.md", "# one\n")
        _write(sandbox.source / "agents" / "two.md", "# two\n")
        _begin_interrupted(["agents"])  # crash before any file was copied

        outcome = recovery_service.resume_interrupted()

        assert (sandbox.target / "agents" / "one.md").read_text(
            encoding="utf-8"
        ) == "# one\n"
        assert (sandbox.target / "agents" / "two.md").read_text(
            encoding="utf-8"
        ) == "# two\n"
        assert outcome.created == 2
        assert install_manifest.load_manifest().status == "complete"
        assert recovery_service.interrupted_state() is None

    def test_raises_when_no_interrupted_manifest_to_resume(self, sandbox):
        with pytest.raises(recovery_service.NoInterruptedApplyError):
            recovery_service.resume_interrupted()


class TestRollbackFreshInstall:
    def test_rollback_deletes_matching_created_files_skips_edited_and_keeps_unmanaged(
        self, sandbox
    ):
        _write(sandbox.source / "agents" / "one.md", "# one\n")
        _write(sandbox.source / "agents" / "two.md", "# two\n")
        plan = _begin_interrupted(["agents"])
        apply_statuses([pf.status for pf in plan])  # both written before the crash
        _write(sandbox.target / "agents" / "mine.md", "# mine\n")  # unmanaged file
        (sandbox.target / "agents" / "two.md").write_text(
            "# two (edited)\n", encoding="utf-8"
        )  # hand-edited before recovery runs

        result = recovery_service.rollback_interrupted()

        assert not (sandbox.target / "agents" / "one.md").exists()
        assert (sandbox.target / "agents" / "two.md").read_text(
            encoding="utf-8"
        ) == "# two (edited)\n"
        assert any(
            "two.md" in entry and "user-modified" in entry for entry in result.skipped
        )
        assert (sandbox.target / "agents" / "mine.md").read_text(
            encoding="utf-8"
        ) == "# mine\n"
        assert not install_manifest.manifest_path().exists()
        assert result.previous_manifest_restored is False
        assert result.deleted == 1

    def test_raises_when_no_interrupted_manifest_to_roll_back(self, sandbox):
        with pytest.raises(recovery_service.NoInterruptedApplyError):
            recovery_service.rollback_interrupted()


class TestRollbackUpgrade:
    def test_rollback_restores_backup_and_previous_complete_manifest_from_history(
        self, sandbox
    ):
        _write(sandbox.source / "agents" / "one.md", "# v1\n")
        apply_components(["agents"])  # first full apply -> complete manifest v1
        v1_manifest = install_manifest.load_manifest()
        old_bytes = (sandbox.target / "agents" / "one.md").read_bytes()

        _write(sandbox.source / "agents" / "one.md", "# v2\n")
        backup_root = install_manifest.manifest_dir() / "backups" / "20260201-000000"
        backup_root.mkdir(parents=True)
        (backup_root / "one.md").write_bytes(old_bytes)

        [pf] = build_plan(["agents"])  # single CHANGED entry: v1 -> v2
        entry = ManagedFile(
            component=pf.component,
            rel=Path(pf.status.rel).as_posix(),
            sha256=install_manifest.sha256_file(pf.status.src),
            action="updated",
            backup="one.md",
        )
        manifest2 = InstallManifest(
            tool_version=cabal.__version__,
            source_mode=install_manifest.current_source_mode(),
            applied_at=datetime.now(UTC).isoformat(),
            status="in_progress",
            components=["agents"],
            backup_dir=str(backup_root),
            files=[entry],
        )
        install_manifest.begin_apply(manifest2)  # rotates v1 into history
        apply_statuses([pf.status])  # new content written just before the crash

        history_before = list(install_manifest.history_dir().glob("*.json"))
        assert len(history_before) == 1

        result = recovery_service.rollback_interrupted()

        assert (sandbox.target / "agents" / "one.md").read_bytes() == old_bytes
        assert result.restored == 1
        assert result.previous_manifest_restored is True
        restored_manifest = install_manifest.load_manifest()
        assert restored_manifest.status == "complete"
        assert restored_manifest.applied_at == v1_manifest.applied_at
