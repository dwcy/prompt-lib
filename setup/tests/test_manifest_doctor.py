# -*- coding: utf-8 -*-
"""Manifest-aware doctor + targeted repair tests (016-install-wizard US3 / T018)."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

import cabal
from cabal import _paths as cabal_paths
from cabal import components as cabal_components
from cabal import install_manifest
from cabal import settings_helpers as cabal_settings_helpers
from cabal.headless import main as headless_main
from cabal.install_manifest import InstallManifest, ManagedFile
from cabal.manifest_doctor import manifest_findings, manifest_status
from cabal.repair_service import repair, repair_plan

# Categories manifest_doctor.py can raise — a healthy sandbox must show none of them.
MANIFEST_DOCTOR_CATEGORIES = {
    "missing-managed-file",
    "stale-manifest",
    "user-modified",
    "interrupted-apply",
    "version-skew",
    "manifest-tampered",
}


@dataclass
class Sandbox:
    source: Path
    target: Path


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Sandbox:
    """Isolated `global/` source payload + `~/.claude/` deploy target.

    Deliberately seeds only components ``config_doctor.run_doctor`` never scans
    (settings/claude_md/rules) so "healthy" assertions aren't polluted by
    unrelated config findings (e.g. agents/*.md missing frontmatter).
    """
    source = tmp_path / "global_src"
    target = tmp_path / ".claude"
    (source / "rules").mkdir(parents=True)

    (source / "settings.json").write_text(
        json.dumps({"theme": "dark"}, indent=2) + "\n", encoding="utf-8"
    )
    (source / "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")
    (source / "rules" / "one.md").write_text("# rule one\n", encoding="utf-8")

    monkeypatch.setattr(cabal_paths, "TARGET", target, raising=True)
    monkeypatch.setattr(cabal_paths, "GLOBAL_DIR", source, raising=True)
    monkeypatch.setattr(cabal_components, "GLOBAL_DIR", source, raising=True)
    monkeypatch.setattr(cabal_components, "TARGET", target, raising=True)
    monkeypatch.setattr(cabal_settings_helpers, "GLOBAL_DIR", source, raising=True)

    return Sandbox(source=source, target=target)


def _read_manifest_json(sandbox: Sandbox) -> dict:
    path = sandbox.target / ".cabal" / "install-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _in_progress_manifest() -> InstallManifest:
    return InstallManifest(
        tool_version=cabal.__version__,
        source_mode=install_manifest.current_source_mode(),
        applied_at="2026-01-01T00:00:00+00:00",
        status="in_progress",
        components=["settings", "claude_md"],
        backup_dir=None,
        files=[],
    )


@pytest.fixture
def repair_scenario(sandbox: Sandbox) -> Sandbox:
    """Healthy install, then one deleted, one hand-edited, one redeployed-outside-cabal file.

    ``settings.json`` plays the hand-edited (user-modified) role rather than the
    deleted/stale roles: it deploys via ``_effective_settings_text`` written through
    ``Path.write_text``, which applies platform newline translation on Windows, so a
    raw byte-for-byte comparison against the source file (as the deleted/stale
    assertions do) would fail there for reasons unrelated to repair correctness.
    """
    headless_main(["apply", "--yes"])
    (sandbox.target / "CLAUDE.md").unlink()
    (sandbox.target / "settings.json").write_text(
        json.dumps({"theme": "hand-edited"}, indent=2) + "\n", encoding="utf-8"
    )
    (sandbox.source / "rules" / "one.md").write_text("# rule one v2\n", encoding="utf-8")
    shutil.copy2(sandbox.source / "rules" / "one.md", sandbox.target / "rules" / "one.md")
    return sandbox


# --- manifest_status() -------------------------------------------------------


def test_manifest_status_absent_when_no_manifest_file(sandbox):
    assert manifest_status() == "absent"


def test_manifest_status_present_complete_after_apply(sandbox):
    headless_main(["apply", "--yes"])

    assert manifest_status() == "present-complete"


def test_manifest_status_present_in_progress_when_interrupted(sandbox):
    install_manifest.begin_apply(_in_progress_manifest())

    assert manifest_status() == "present-in-progress"


# --- `cabal doctor` -----------------------------------------------------------


def test_doctor_after_fresh_apply_reports_no_manifest_findings_and_exits_zero(
    sandbox, capsys
):
    headless_main(["apply", "--yes"])
    capsys.readouterr()

    exit_code = headless_main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)

    categories = {f["category"] for f in payload["findings"]}
    assert exit_code == 0
    assert categories.isdisjoint(MANIFEST_DOCTOR_CATEGORIES)


def test_doctor_reports_missing_managed_file_as_error_and_exits_one(sandbox, capsys):
    headless_main(["apply", "--yes"])
    capsys.readouterr()
    (sandbox.target / "rules" / "one.md").unlink()

    exit_code = headless_main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    findings = {f["category"]: f for f in payload["findings"]}

    assert findings["missing-managed-file"]["severity"] == "error"
    assert exit_code == 1


def test_doctor_reports_hand_edited_file_as_user_modified_warning_and_exits_zero(
    sandbox, capsys
):
    headless_main(["apply", "--yes"])
    capsys.readouterr()
    (sandbox.target / "rules" / "one.md").write_text("# hand edited\n", encoding="utf-8")

    exit_code = headless_main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    findings = {f["category"]: f for f in payload["findings"]}

    assert findings["user-modified"]["severity"] == "warning"
    assert exit_code == 0


def test_doctor_reports_redeployed_file_as_stale_manifest_warning_and_exits_zero(
    sandbox, capsys
):
    headless_main(["apply", "--yes"])
    capsys.readouterr()
    (sandbox.source / "rules" / "one.md").write_text("# rule one v2\n", encoding="utf-8")
    shutil.copy2(sandbox.source / "rules" / "one.md", sandbox.target / "rules" / "one.md")

    exit_code = headless_main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    findings = {f["category"]: f for f in payload["findings"]}

    assert findings["stale-manifest"]["severity"] == "warning"
    assert exit_code == 0


def test_doctor_reports_interrupted_apply_as_error_and_exits_one(sandbox, capsys):
    install_manifest.begin_apply(_in_progress_manifest())

    exit_code = headless_main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    findings = {f["category"]: f for f in payload["findings"]}

    assert findings["interrupted-apply"]["severity"] == "error"
    assert exit_code == 1


def test_doctor_reports_version_skew_as_warning_and_exits_zero(
    sandbox, capsys, monkeypatch
):
    headless_main(["apply", "--yes"])
    capsys.readouterr()
    monkeypatch.setattr(cabal, "__version__", "9.9.9", raising=True)

    exit_code = headless_main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    findings = {f["category"]: f for f in payload["findings"]}

    assert findings["version-skew"]["severity"] == "warning"
    assert exit_code == 0


def test_doctor_without_manifest_exits_five_and_reports_absent_in_json(sandbox, capsys):
    exit_code = headless_main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 5
    assert payload["manifest"]["present"] is False
    assert payload["findings"] == []


def test_doctor_reports_tampered_manifest_as_error_and_exits_one_not_five(
    sandbox, capsys
):
    headless_main(["apply", "--yes"])
    capsys.readouterr()
    manifest = install_manifest.load_manifest()
    manifest.files.append(
        ManagedFile(
            component="rules", rel="../evil.md", sha256="0" * 64, action="created"
        )
    )
    install_manifest.save_manifest(manifest)

    exit_code = headless_main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    findings = {f["category"]: f for f in payload["findings"]}

    assert findings["manifest-tampered"]["severity"] == "error"
    assert exit_code == 1


# --- targeted repair -----------------------------------------------------------


def test_repair_plan_includes_missing_and_stale_but_excludes_user_modified(
    repair_scenario,
):
    plan = repair_plan()

    assert set(plan) == {("claude_md", "CLAUDE.md"), ("rules", "one.md")}


def test_repair_restores_missing_and_stale_files_to_current_source_content(
    repair_scenario,
):
    repair()

    claude_md_sha = install_manifest.sha256_file(repair_scenario.target / "CLAUDE.md")
    rules_sha = install_manifest.sha256_file(repair_scenario.target / "rules" / "one.md")
    assert claude_md_sha == install_manifest.sha256_file(repair_scenario.source / "CLAUDE.md")
    assert rules_sha == install_manifest.sha256_file(
        repair_scenario.source / "rules" / "one.md"
    )


def test_repair_leaves_user_modified_file_untouched(repair_scenario):
    repair()

    settings = json.loads(
        (repair_scenario.target / "settings.json").read_text(encoding="utf-8")
    )
    assert settings == {"theme": "hand-edited"}


def test_repair_result_manifest_is_complete_inventory_of_all_three_files(
    repair_scenario,
):
    repair()

    manifest = install_manifest.load_manifest()
    entries = {(e.component, e.rel) for e in manifest.files}
    assert entries == {
        ("settings", "settings.json"),
        ("claude_md", "CLAUDE.md"),
        ("rules", "one.md"),
    }


def test_repair_keeps_user_modified_entrys_original_hash_so_doctor_still_flags_it(
    repair_scenario,
):
    before = install_manifest.load_manifest()
    before_hash = next(e.sha256 for e in before.files if e.component == "settings")

    repair()

    after = install_manifest.load_manifest()
    after_hash = next(e.sha256 for e in after.files if e.component == "settings")
    categories = {f.category for f in manifest_findings(after)}
    assert (after_hash, "user-modified" in categories) == (before_hash, True)
