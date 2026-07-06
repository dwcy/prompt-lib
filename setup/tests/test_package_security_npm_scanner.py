# -*- coding: utf-8 -*-
"""Unit tests for the npm/pnpm/bun package security scanner — subprocess.run mocked."""

from __future__ import annotations

import json

import pytest

from cabal.package_security import npm_scanner


class _FakeCompletedProcess:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.returncode = 1  # audit/outdated exit non-zero when findings exist


@pytest.fixture(autouse=True)
def _fake_binary_resolution(monkeypatch):
    monkeypatch.setattr(npm_scanner.shutil, "which", lambda name: f"/usr/bin/{name}")


def test_detect_package_manager_prefers_pnpm_lockfile(tmp_path):
    (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")

    assert npm_scanner._detect_package_manager(tmp_path) == "pnpm"


def test_detect_package_manager_prefers_bun_lockfile(tmp_path):
    (tmp_path / "bun.lock").write_text("", encoding="utf-8")

    assert npm_scanner._detect_package_manager(tmp_path) == "bun"


def test_detect_package_manager_defaults_to_npm(tmp_path):
    assert npm_scanner._detect_package_manager(tmp_path) == "npm"


def test_scan_npm_parses_npm_v7_audit_and_outdated_json(tmp_path, monkeypatch):
    audit_payload = json.dumps(
        {
            "vulnerabilities": {
                "lodash": {
                    "severity": "high",
                    "range": "<4.17.21",
                    "via": [{"title": "Prototype Pollution"}],
                    "fixAvailable": {"name": "lodash", "version": "4.17.21"},
                }
            }
        }
    )
    outdated_payload = json.dumps({"chalk": {"current": "4.0.0", "latest": "5.3.0"}})
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == "audit":
            return _FakeCompletedProcess(audit_payload)
        return _FakeCompletedProcess(outdated_payload)

    monkeypatch.setattr(npm_scanner.subprocess, "run", _fake_run)
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    outcome = npm_scanner.scan_npm(tmp_path)
    by_package = {f.package: f for f in outcome.findings}

    assert by_package["lodash"].kind == "vulnerable"
    assert by_package["lodash"].target_version == "4.17.21"
    assert by_package["lodash"].fix_command == "npm install lodash@4.17.21"
    assert by_package["chalk"].kind == "outdated"
    assert by_package["chalk"].fix_command == "npm install chalk@5.3.0"


def test_scan_npm_parses_pnpm_legacy_advisories_format(tmp_path, monkeypatch):
    audit_payload = json.dumps(
        {
            "advisories": {
                "1": {
                    "module_name": "lodash",
                    "severity": "high",
                    "patched_versions": ">=4.17.21",
                    "title": "Command Injection",
                    "findings": [{"version": "4.17.15"}],
                }
            }
        }
    )

    def _fake_run(cmd, **kwargs):
        if "audit" in cmd:
            return _FakeCompletedProcess(audit_payload)
        return _FakeCompletedProcess("{}")

    monkeypatch.setattr(npm_scanner.subprocess, "run", _fake_run)
    (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")

    outcome = npm_scanner.scan_npm(tmp_path)
    finding = next(f for f in outcome.findings if f.package == "lodash")

    assert finding.current_version == "4.17.15"
    assert finding.target_version == "4.17.21"
    assert finding.fix_command == "pnpm add lodash@4.17.21"


def test_scan_npm_parses_bun_audit_without_patched_version(tmp_path, monkeypatch):
    audit_payload = json.dumps(
        {"lodash": [{"severity": "high", "vulnerable_versions": "<4.17.21", "title": "ReDoS"}]}
    )
    bun_outdated_table = (
        "bun outdated v1.3.14\n"
        "|---------------------------------------|\n"
        "| Package  | Current | Update  | Latest |\n"
        "|----------|---------|---------|--------|\n"
        "| lodash   | 4.17.15 | 4.17.15 | 4.18.1 |\n"
        "|---------------------------------------|\n"
    )

    def _fake_run(cmd, **kwargs):
        if "audit" in cmd:
            return _FakeCompletedProcess(audit_payload)
        return _FakeCompletedProcess(bun_outdated_table)

    monkeypatch.setattr(npm_scanner.subprocess, "run", _fake_run)
    (tmp_path / "bun.lock").write_text("", encoding="utf-8")

    outcome = npm_scanner.scan_npm(tmp_path)
    by_kind = {f.kind: f for f in outcome.findings}

    assert by_kind["vulnerable"].target_version is None
    assert by_kind["vulnerable"].fix_command is None
    assert by_kind["outdated"].target_version == "4.18.1"
    assert by_kind["outdated"].fix_command == "bun add lodash@4.18.1"


def test_scan_npm_reports_notice_when_manager_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(npm_scanner.shutil, "which", lambda name: None)

    outcome = npm_scanner.scan_npm(tmp_path)

    assert outcome.findings == ()
    assert any("not found on PATH" in n for n in outcome.notices)


def test_scan_npm_reports_notice_on_malformed_audit_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        npm_scanner.subprocess,
        "run",
        lambda cmd, **kwargs: _FakeCompletedProcess("not json"),
    )

    outcome = npm_scanner.scan_npm(tmp_path)

    assert outcome.findings == ()
    assert any("Could not parse" in n for n in outcome.notices)
