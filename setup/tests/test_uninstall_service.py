# -*- coding: utf-8 -*-
"""Behaviour contract tests for headless `cabal uninstall` and UninstallScreen (016-T022)."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import DataTable, Static

import cabal
from cabal import _paths as cabal_paths
from cabal import components as cabal_components
from cabal import install_manifest
from cabal import settings_helpers as cabal_settings_helpers
from cabal.headless import main as headless_main
from cabal.install_manifest import InstallManifest
from cabal.uninstall_service import UninstallItem, UninstallPlan
from cabal.views import uninstall as uninstall_view
from cabal.views.uninstall import UninstallScreen


@dataclass
class Sandbox:
    source: Path
    target: Path


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Sandbox:
    """Isolated `global/` source payload + `~/.claude/` deploy target.

    Same seam-patching pattern as test_headless_cli.py's sandbox: every module
    that binds GLOBAL_DIR/TARGET at import time is patched so uninstall never
    touches the real HOME.
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


# --- manifest-driven removal (US4 AC1) --------------------------------------


def test_uninstall_yes_removes_manifest_files_and_keeps_unmanaged_file(sandbox, capsys):
    headless_main(["apply", "--yes"])
    capsys.readouterr()
    unmanaged = sandbox.target / "agents" / "mine.md"
    unmanaged.write_text("# mine\n", encoding="utf-8")

    exit_code = headless_main(["uninstall", "--json", "--yes"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert not (sandbox.target / "settings.json").exists()
    assert not (sandbox.target / "CLAUDE.md").exists()
    assert not (sandbox.target / "agents" / "one.md").exists()
    assert not (sandbox.target / "hooks" / "h.py").exists()
    assert unmanaged.read_text(encoding="utf-8") == "# mine\n"
    assert payload["status"] == "uninstalled"
    assert payload["counts"] == {
        "removed": 4,
        "skipped": 0,
        "missing": 0,
        "restored": 0,
    }


# --- user-modified files are skipped, not removed (US4 AC2) ----------------


def test_uninstall_yes_skips_user_modified_file_reported_in_json_counts(
    sandbox, capsys
):
    headless_main(["apply", "--yes"])
    capsys.readouterr()
    (sandbox.target / "agents" / "one.md").write_text(
        "# hand edited\n", encoding="utf-8"
    )

    exit_code = headless_main(["uninstall", "--json", "--yes"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert (sandbox.target / "agents" / "one.md").read_text(
        encoding="utf-8"
    ) == "# hand edited\n"
    assert payload["counts"]["skipped"] == 1
    assert payload["counts"]["removed"] == 3


def test_uninstall_yes_reports_user_modified_reason_in_plain_text_summary(
    sandbox, capsys
):
    headless_main(["apply", "--yes"])
    capsys.readouterr()
    (sandbox.target / "agents" / "one.md").write_text(
        "# hand edited\n", encoding="utf-8"
    )

    exit_code = headless_main(["uninstall", "--yes"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "one.md" in output
    assert "user-modified" in output
    assert (sandbox.target / "agents" / "one.md").exists()


# --- backup restoration (US4 AC3) -------------------------------------------


def test_uninstall_restore_backups_returns_preinstall_content(sandbox, capsys):
    sandbox.target.mkdir(parents=True)
    original_claude_md = "# original pre-install CLAUDE\n"
    (sandbox.target / "CLAUDE.md").write_text(original_claude_md, encoding="utf-8")

    headless_main(["apply", "--yes"])
    capsys.readouterr()
    assert (
        sandbox.target / "CLAUDE.md"
    ).read_text(encoding="utf-8") != original_claude_md

    exit_code = headless_main(["uninstall", "--json", "--yes", "--restore-backups"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["counts"]["restored"] == 1
    assert (
        sandbox.target / "CLAUDE.md"
    ).read_text(encoding="utf-8") == original_claude_md


# --- .cabal state dir removed last, only on success (US4 AC4) --------------


def test_uninstall_yes_removes_state_dir_on_clean_success(sandbox, capsys):
    headless_main(["apply", "--yes"])
    capsys.readouterr()

    exit_code = headless_main(["uninstall", "--yes"])

    assert exit_code == 0
    assert not (sandbox.target / ".cabal").exists()


def test_uninstall_yes_with_per_file_error_keeps_manifest_and_state_dir_for_rerun(
    sandbox, capsys, monkeypatch
):
    headless_main(["apply", "--yes"])
    capsys.readouterr()
    original_unlink = Path.unlink

    def flaky_unlink(self: Path, *args, **kwargs):
        if self.name == "one.md":
            raise OSError("simulated disk error")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)

    exit_code = headless_main(["uninstall", "--json", "--yes"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "error"
    assert _manifest_path(sandbox).exists()
    assert (sandbox.target / ".cabal").exists()


# --- no manifest: --legacy gate (US4 AC5) -----------------------------------


def test_uninstall_without_manifest_exits_five_and_reports_no_manifest_status(
    sandbox, capsys
):
    exit_code = headless_main(["uninstall", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 5
    assert payload["status"] == "no-manifest"


def test_uninstall_legacy_dry_run_classifies_source_matching_file_as_remove(
    sandbox, capsys
):
    (sandbox.target / "agents").mkdir(parents=True)
    shutil.copy2(sandbox.source / "CLAUDE.md", sandbox.target / "CLAUDE.md")
    (sandbox.target / "agents" / "one.md").write_text(
        "# hand written, never deployed by cabal\n", encoding="utf-8"
    )

    exit_code = headless_main(["uninstall", "--legacy", "--dry-run", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "dry-run"
    assert payload["counts"]["removed"] == 1
    assert payload["counts"]["skipped"] == 1
    assert (sandbox.target / "CLAUDE.md").exists()
    assert (sandbox.target / "agents" / "one.md").exists()


# --- confirmation required (US4 AC6) ----------------------------------------


def test_uninstall_without_yes_and_nonempty_plan_requires_confirmation(
    sandbox, capsys
):
    headless_main(["apply", "--yes"])
    capsys.readouterr()

    exit_code = headless_main(["uninstall"])

    assert exit_code == 3
    assert (sandbox.target / "CLAUDE.md").exists()
    assert (sandbox.target / ".cabal").exists()


# --- dry run removes nothing (US4 AC7) --------------------------------------


def test_uninstall_dry_run_removes_nothing_and_keeps_state_dir(sandbox, capsys):
    headless_main(["apply", "--yes"])
    capsys.readouterr()

    exit_code = headless_main(["uninstall", "--dry-run", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "dry-run"
    assert (sandbox.target / "CLAUDE.md").exists()
    assert (sandbox.target / ".cabal").exists()


# --- interrupted apply blocks uninstall (US4 AC8) ---------------------------


def test_uninstall_with_interrupted_manifest_refuses_and_mentions_recovery(
    sandbox, capsys
):
    _write_in_progress_manifest(sandbox)

    exit_code = headless_main(["uninstall", "--yes"])
    stderr = capsys.readouterr().err

    assert exit_code == 1
    assert "recovery" in stderr.lower()


# --- UninstallScreen mount-and-render smoke (US4 AC9) -----------------------


@pytest.mark.asyncio
async def test_uninstall_screen_renders_plan_preview(sandbox, monkeypatch):
    plan = UninstallPlan(
        legacy=False,
        manifest=None,
        remove=[
            UninstallItem("agents", "one.md", sandbox.target / "agents" / "one.md")
        ],
        skip=[
            UninstallItem(
                "agents", "mine.md", None, reason="user-modified — kept on disk"
            )
        ],
        missing=[],
    )
    monkeypatch.setattr(uninstall_view, "uninstall_plan", lambda legacy=False: plan)

    app = App()
    async with app.run_test() as pilot:
        await app.push_screen(UninstallScreen())
        await app.workers.wait_for_complete()
        await pilot.pause()

        summary = str(app.screen.query_one("#unst-summary", Static).render())
        row_count = app.screen.query_one("#unst-table", DataTable).row_count

    assert "1 to remove" in summary
    assert row_count == 2
