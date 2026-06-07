"""Tests for setup/tools/settings_merge.py — add-only merge, manifest, uninstall."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import settings_merge  # noqa: E402


@pytest.fixture
def tmp_target(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings_merge, "TARGET", target, raising=True)
    monkeypatch.setattr(
        settings_merge,
        "MANIFEST_PATH",
        target / ".promptlib-applied.json",
        raising=True,
    )
    return target


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class TestMergeSettings:
    def test_returns_src_when_dst_missing(self, tmp_path):
        src, dst = tmp_path / "src.json", tmp_path / "dst.json"
        _write_json(src, {"theme": "dark", "model": "opus"})
        assert settings_merge.merge_settings(src, dst) == {
            "theme": "dark",
            "model": "opus",
        }

    def test_raises_on_unparseable_dst(self, tmp_path):
        src, dst = tmp_path / "src.json", tmp_path / "dst.json"
        _write_json(src, {"theme": "dark"})
        dst.write_text("{ this is not json", encoding="utf-8")
        with pytest.raises(ValueError) as excinfo:
            settings_merge.merge_settings(src, dst)
        assert str(dst) in str(excinfo.value)

    def test_top_level_overwrite_preserve_and_add(self, tmp_path):
        src, dst = tmp_path / "src.json", tmp_path / "dst.json"
        _write_json(src, {"shared": "from-src", "src_only": 1})
        _write_json(dst, {"shared": "from-dst", "dst_only": 2})
        result = settings_merge.merge_settings(src, dst)
        assert result["shared"] == "from-src"
        assert result["src_only"] == 1
        assert result["dst_only"] == 2

    def test_one_level_nested_map_merge(self, tmp_path):
        src, dst = tmp_path / "src.json", tmp_path / "dst.json"
        _write_json(
            src, {"mcpServers": {"global_a": {"cmd": "a"}, "shared": {"cmd": "src"}}}
        )
        _write_json(
            dst, {"mcpServers": {"user_b": {"cmd": "b"}, "shared": {"cmd": "dst"}}}
        )
        result = settings_merge.merge_settings(src, dst)
        assert result["mcpServers"]["global_a"] == {"cmd": "a"}
        assert result["mcpServers"]["user_b"] == {"cmd": "b"}
        assert result["mcpServers"]["shared"] == {"cmd": "src"}

    def test_list_dedup_and_merge(self, tmp_path):
        src, dst = tmp_path / "src.json", tmp_path / "dst.json"
        _write_json(src, {"items": ["a", "b", "shared"]})
        _write_json(dst, {"items": ["shared", "c"]})
        result = settings_merge.merge_settings(src, dst)
        assert result["items"].count("shared") == 1
        assert {"a", "b", "c"} <= set(result["items"])


class TestManifestRoundTrip:
    def test_write_then_read_roundtrip(self, tmp_target):
        f1 = tmp_target / "settings.json"
        f2 = tmp_target / "agents" / "x.md"
        f1.write_text("hello", encoding="utf-8")
        f2.parent.mkdir(parents=True, exist_ok=True)
        f2.write_text("world", encoding="utf-8")
        settings_merge.write_manifest([f1, f2])
        entries = settings_merge.read_manifest()
        assert {e.path for e in entries} == {"settings.json", "agents/x.md"}
        assert all(len(e.sha256) == 64 for e in entries)

    def test_manifest_payload_shape(self, tmp_target):
        f = tmp_target / "settings.json"
        f.write_text("hello", encoding="utf-8")
        settings_merge.write_manifest([f])
        payload = json.loads(settings_merge.MANIFEST_PATH.read_text(encoding="utf-8"))
        assert payload["version"] == 1
        assert "applied_at" in payload
        assert payload["files"][0]["path"] == "settings.json"

    def test_write_manifest_updates_touched_entry(self, tmp_target):
        f = tmp_target / "a.txt"
        f.write_text("v1", encoding="utf-8")
        settings_merge.write_manifest([f])
        first = next(e for e in settings_merge.read_manifest() if e.path == "a.txt")
        f.write_text("v2-different", encoding="utf-8")
        settings_merge.write_manifest([f])
        second = next(e for e in settings_merge.read_manifest() if e.path == "a.txt")
        assert first.sha256 != second.sha256


class TestUninstall:
    def test_no_manifest_returns_zero_with_message(self, tmp_target, capsys):
        rc = settings_merge._uninstall()
        assert rc == 0
        assert "No manifest found" in capsys.readouterr().out

    def test_removes_matching_skips_modified(self, tmp_target):
        clean = tmp_target / "clean.txt"
        modified = tmp_target / "modified.txt"
        clean.write_text("clean-content", encoding="utf-8")
        modified.write_text("original", encoding="utf-8")
        settings_merge.write_manifest([clean, modified])
        modified.write_text("user-edited", encoding="utf-8")

        rc = settings_merge._uninstall()
        assert rc == 0
        assert not clean.exists()
        assert (
            modified.exists() and modified.read_text(encoding="utf-8") == "user-edited"
        )
        assert {e.path for e in settings_merge.read_manifest()} == {"modified.txt"}

    def test_deletes_manifest_when_all_removed(self, tmp_target):
        f = tmp_target / "only.txt"
        f.write_text("data", encoding="utf-8")
        settings_merge.write_manifest([f])
        rc = settings_merge._uninstall()
        assert rc == 0
        assert not f.exists()
        assert not settings_merge.MANIFEST_PATH.exists()
