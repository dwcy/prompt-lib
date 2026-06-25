"""Runtime backup record tests."""

from __future__ import annotations

import json
from pathlib import Path

import cabal.installers.runtime_backups as backups


def test_runtime_backup_record_created_before_install(monkeypatch, tmp_path):
    monkeypatch.setattr(backups.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(backups, "installed_version_for", lambda key: "1.2.3")
    monkeypatch.setattr(backups, "safe_config_paths", lambda key: ())

    record = backups.create_runtime_backup_record("node", root=tmp_path)

    assert record.tool_key == "node"
    assert record.before_version == "1.2.3"
    assert record.before_path == "/usr/bin/node"
    assert record.artifact_path is not None
    payload = json.loads(Path(record.artifact_path).read_text(encoding="utf-8"))
    assert payload["tool_key"] == "node"


def test_backup_failure_blocks_or_requires_confirmation(monkeypatch):
    def boom(tool_key: str):
        raise OSError("no write")

    monkeypatch.setattr(backups, "create_runtime_backup_record", boom)

    ok, message = backups.backup_before_install("node")

    assert ok is False
    assert "Runtime backup failed" in message


def test_restore_hint_is_present_for_each_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(backups.shutil, "which", lambda name: None)
    monkeypatch.setattr(backups, "installed_version_for", lambda key: None)
    monkeypatch.setattr(backups, "safe_config_paths", lambda key: ())

    for key in sorted(backups.RUNTIME_BACKUP_KEYS):
        record = backups.create_runtime_backup_record(key, root=tmp_path)
        assert "Restore" in record.restore_hint
