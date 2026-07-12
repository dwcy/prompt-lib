# -*- coding: utf-8 -*-
"""Behaviour contract tests for the headless `cabal apply` / `--version` CLI (016-T005)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

# Module-level import: this MUST fail with ModuleNotFoundError until the
# headless layer (specs/016-install-wizard/contracts/cli-contract.md) exists.
from cabal.headless import main as headless_main

from cabal.__main__ import main as cli_main

import cabal
from cabal import _paths as cabal_paths
from cabal import components as cabal_components
from cabal import install_manifest
from cabal import settings_helpers as cabal_settings_helpers
from cabal.install_manifest import InstallManifest

VERSION_PATTERN = r"^cabal \d+\.\d+\.\d+ \((source|wheel|frozen)\)"

ENTRY_POINTS = {"headless": headless_main, "cli_main": cli_main}


@dataclass
class Sandbox:
    source: Path
    target: Path


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Sandbox:
    """Isolated `global/` source payload + `~/.claude/` deploy target.

    Patches every seam that binds GLOBAL_DIR/TARGET at import time
    (components.py, settings_helpers.py) plus cabal._paths itself, which
    install_manifest resolves lazily via module-attribute access.
    """
    source = tmp_path / "global_src"
    target = tmp_path / ".claude"
    (source / "agents").mkdir(parents=True)
    (source / "hooks").mkdir(parents=True)

    (source / "settings.json").write_text(
        json.dumps({"theme": "dark"}, indent=2) + "\n", encoding="utf-8"
    )
    (source / "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")
    (source / "agents" / "one.md").write_text("# one\n", encoding="utf-8")
    (source / "hooks" / "h.py").write_text("print('hook')\n", encoding="utf-8")

    monkeypatch.setattr(cabal_paths, "TARGET", target, raising=True)
    monkeypatch.setattr(cabal_paths, "GLOBAL_DIR", source, raising=True)
    monkeypatch.setattr(cabal_components, "GLOBAL_DIR", source, raising=True)
    monkeypatch.setattr(cabal_components, "TARGET", target, raising=True)
    monkeypatch.setattr(cabal_settings_helpers, "GLOBAL_DIR", source, raising=True)

    return Sandbox(source=source, target=target)


def _manifest_path(sandbox: Sandbox) -> Path:
    return sandbox.target / ".cabal" / "install-manifest.json"


def _write_in_progress_manifest(sandbox: Sandbox) -> None:
    manifest = InstallManifest(
        tool_version=cabal.__version__,
        source_mode=install_manifest.current_source_mode(),
        applied_at="2026-01-01T00:00:00+00:00",
        status="in_progress",
        components=["settings", "claude_md"],
        backup_dir=None,
        files=[],
    )
    install_manifest.begin_apply(manifest)


# Component keys deployed as a subdirectory of the sandbox target; file-type
# components (settings, claude_md) deploy directly under the target root, so
# their manifest `rel` is already the full destination filename.
_DIR_COMPONENT_ROOTS: dict[str, str] = {"agents": "agents", "hooks": "hooks"}

# The sandbox fixture seeds exactly these four files across four components.
EXPECTED_MANIFEST_ENTRIES: set[tuple[str, str]] = {
    ("settings", "settings.json"),
    ("claude_md", "CLAUDE.md"),
    ("agents", "one.md"),
    ("hooks", "h.py"),
}


def _read_manifest(sandbox: Sandbox) -> dict:
    return json.loads(_manifest_path(sandbox).read_text(encoding="utf-8"))


def _deployed_path(sandbox: Sandbox, component: str, rel: str) -> Path:
    root = sandbox.target / _DIR_COMPONENT_ROOTS.get(component, "")
    return root / rel


def _sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk_hashes(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        str(p.relative_to(root)): _sha256_bytes(p) for p in root.rglob("*") if p.is_file()
    }


def _apply_twice_with_one_file_changed(
    call, sandbox: Sandbox, capsys: pytest.CaptureFixture[str]
) -> tuple[dict, dict, bytes]:
    """Fresh install, then a second apply after editing `agents/one.md`.

    Returns the second apply's JSON payload, the manifest read back off disk,
    and the pre-edit bytes of the deployed file (for backup-content assertions).
    """
    call(["apply", "--yes"])
    capsys.readouterr()
    old_bytes = _deployed_path(sandbox, "agents", "one.md").read_bytes()

    (sandbox.source / "agents" / "one.md").write_text(
        "# one changed\n", encoding="utf-8"
    )
    call(["apply", "--json", "--yes"])
    payload = json.loads(capsys.readouterr().out)
    manifest = _read_manifest(sandbox)
    return payload, manifest, old_bytes


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_version_flag_prints_version_and_exits_zero(call, capsys):
    exit_code = call(["--version"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert re.match(VERSION_PATTERN, captured.out.strip())


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_dry_run_reports_planned_files_and_writes_nothing(call, sandbox, capsys):
    exit_code = call(["apply", "--dry-run"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert not sandbox.target.exists()
    assert "settings.json" in captured.out
    assert "CLAUDE.md" in captured.out


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_apply_without_yes_and_pending_changes_requires_confirmation(call, sandbox):
    exit_code = call(["apply"])

    assert exit_code == 3
    assert not sandbox.target.exists()


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_apply_yes_deploys_files_and_writes_complete_manifest(call, sandbox):
    exit_code = call(["apply", "--yes"])

    assert exit_code == 0
    assert (sandbox.target / "settings.json").exists()
    assert (sandbox.target / "CLAUDE.md").exists()
    manifest = json.loads(_manifest_path(sandbox).read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_apply_json_yes_outputs_applied_status_with_contract_keys(call, sandbox, capsys):
    exit_code = call(["apply", "--json", "--yes"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "applied"
    assert set(payload) == {
        "status",
        "tool_version",
        "components",
        "counts",
        "backup_dir",
        "manifest",
    }


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_second_apply_with_no_changes_reports_up_to_date(call, sandbox, capsys):
    call(["apply", "--yes"])
    capsys.readouterr()

    exit_code = call(["apply", "--json", "--yes"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "up-to-date"
    assert payload["counts"]["created"] == 0
    assert payload["counts"]["updated"] == 0


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_components_filter_keeps_required_core_adds_requested_skips_rest(
    call, sandbox
):
    exit_code = call(["apply", "--components", "agents", "--yes"])

    assert exit_code == 0
    assert (sandbox.target / "settings.json").exists()
    assert (sandbox.target / "CLAUDE.md").exists()
    assert (sandbox.target / "agents" / "one.md").exists()
    assert not (sandbox.target / "hooks").exists()


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_apply_unknown_component_key_is_usage_error_and_writes_nothing(call, sandbox):
    exit_code = call(["apply", "--components", "nope", "--yes"])

    assert exit_code == 2
    assert not sandbox.target.exists()


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_apply_unknown_flag_is_usage_error(call, sandbox):
    exit_code = call(["apply", "--bogus"])

    assert exit_code == 2


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_declined_apply_with_pending_changes_leaves_deploy_tree_byte_identical(
    call, sandbox
):
    call(["apply", "--yes"])
    (sandbox.source / "agents" / "one.md").write_text(
        "# one changed\n", encoding="utf-8"
    )
    before = _walk_hashes(sandbox.target)

    exit_code = call(["apply"])

    assert exit_code == 3
    assert _walk_hashes(sandbox.target) == before


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_unmanaged_file_in_component_dir_survives_apply(call, sandbox):
    call(["apply", "--yes"])
    unmanaged = sandbox.target / "agents" / "mine.md"
    unmanaged.write_text("# mine\n", encoding="utf-8")

    exit_code = call(["apply", "--yes"])

    assert exit_code == 0
    assert unmanaged.read_text(encoding="utf-8") == "# mine\n"


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_apply_without_yes_detects_interrupted_previous_apply(call, sandbox):
    _write_in_progress_manifest(sandbox)

    exit_code = call(["apply"])

    assert exit_code == 4


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_apply_with_yes_resumes_after_interrupted_previous_apply(call, sandbox):
    _write_in_progress_manifest(sandbox)

    exit_code = call(["apply", "--yes"])
    manifest = json.loads(_manifest_path(sandbox).read_text(encoding="utf-8"))

    assert exit_code == 0
    assert manifest["status"] == "complete"


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_apply_yes_manifest_files_is_complete_inventory_of_deployed_sandbox_files(
    call, sandbox
):
    call(["apply", "--yes"])

    manifest = _read_manifest(sandbox)
    entries = [(f["component"], f["rel"]) for f in manifest["files"]]

    assert sorted(entries) == sorted(EXPECTED_MANIFEST_ENTRIES)


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_apply_yes_fresh_install_records_created_action_with_matching_sha256(
    call, sandbox
):
    call(["apply", "--yes"])

    manifest = _read_manifest(sandbox)

    mismatches = [
        entry
        for entry in manifest["files"]
        if entry["action"] != "created"
        or entry["sha256"]
        != _sha256_bytes(
            _deployed_path(sandbox, entry["component"], entry["rel"])
        )
    ]
    assert mismatches == []


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_second_apply_yes_reports_one_updated_file_in_json_counts(
    call, sandbox, capsys
):
    payload, _manifest, _old_bytes = _apply_twice_with_one_file_changed(
        call, sandbox, capsys
    )

    assert payload["counts"] == {
        "created": 0,
        "updated": 1,
        "unchanged": 3,
        "backed_up": 1,
        "skipped": 0,
    }


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_second_apply_yes_backs_up_old_bytes_of_the_changed_file(
    call, sandbox, capsys
):
    _payload, manifest, old_bytes = _apply_twice_with_one_file_changed(
        call, sandbox, capsys
    )

    by_key = {(f["component"], f["rel"]): f for f in manifest["files"]}
    updated = by_key[("agents", "one.md")]
    backup_file = Path(manifest["backup_dir"]) / updated["backup"]

    assert updated["action"] == "updated"
    assert backup_file.is_file()
    assert backup_file.read_bytes() == old_bytes


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_second_apply_yes_leaves_untouched_files_unchanged_with_no_backup_ref(
    call, sandbox, capsys
):
    _payload, manifest, _old_bytes = _apply_twice_with_one_file_changed(
        call, sandbox, capsys
    )

    untouched = [
        f for f in manifest["files"] if (f["component"], f["rel"]) != ("agents", "one.md")
    ]

    assert all(f["action"] == "unchanged" and f["backup"] is None for f in untouched)


@pytest.mark.parametrize("call", ENTRY_POINTS.values(), ids=ENTRY_POINTS.keys())
def test_third_apply_yes_with_no_further_changes_does_not_rewrite_manifest_or_history(
    call, sandbox, capsys
):
    _apply_twice_with_one_file_changed(call, sandbox, capsys)
    manifest_file = _manifest_path(sandbox)
    history_dir = manifest_file.parent / "history"
    before_bytes = manifest_file.read_bytes()
    before_mtime = manifest_file.stat().st_mtime_ns
    before_history = sorted(history_dir.glob("*.json")) if history_dir.exists() else []

    exit_code = call(["apply", "--json", "--yes"])
    payload = json.loads(capsys.readouterr().out)
    after_history = sorted(history_dir.glob("*.json")) if history_dir.exists() else []

    assert exit_code == 0
    assert payload["status"] == "up-to-date"
    assert manifest_file.read_bytes() == before_bytes
    assert manifest_file.stat().st_mtime_ns == before_mtime
    assert after_history == before_history
