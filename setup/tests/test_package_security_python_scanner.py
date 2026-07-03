# -*- coding: utf-8 -*-
"""Unit tests for the Python package security scanner — subprocess.run mocked."""

from __future__ import annotations

import pytest

from cabal.package_security import python_scanner


class _FakeCompletedProcess:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.returncode = 0


def test_scan_python_reports_notice_when_pip_audit_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(python_scanner.shutil, "which", lambda name: None)
    monkeypatch.setattr(python_scanner, "_run_json", lambda cmd: [])

    outcome = python_scanner.scan_python(tmp_path)

    assert outcome.findings == ()
    assert any("pip-audit not installed" in n for n in outcome.notices)


def test_scan_python_parses_vulnerable_and_outdated_happy_path(tmp_path, monkeypatch):
    audit_payload = {
        "dependencies": [
            {
                "name": "requests",
                "version": "2.25.0",
                "vulns": [{"id": "PYSEC-2023-1", "fix_versions": ["2.31.0"]}],
            }
        ]
    }
    outdated_payload = [{"name": "flask", "version": "2.0.0", "latest_version": "3.0.0"}]

    monkeypatch.setattr(python_scanner.shutil, "which", lambda name: "/usr/bin/pip-audit")

    def _fake_run_json(cmd):
        if cmd[0] == "pip-audit":
            return audit_payload
        return outdated_payload

    monkeypatch.setattr(python_scanner, "_run_json", _fake_run_json)

    outcome = python_scanner.scan_python(tmp_path)
    by_package = {f.package: f for f in outcome.findings}

    assert by_package["requests"].kind == "vulnerable"
    assert by_package["requests"].target_version == "2.31.0"
    assert by_package["requests"].fix_command == 'pip install "requests==2.31.0"'
    assert by_package["flask"].kind == "outdated"
    assert by_package["flask"].fix_command == 'pip install "flask==3.0.0"'
    assert outcome.notices == ()


def test_scan_python_returns_no_findings_when_nothing_outdated_or_vulnerable(tmp_path, monkeypatch):
    monkeypatch.setattr(python_scanner.shutil, "which", lambda name: "/usr/bin/pip-audit")
    monkeypatch.setattr(python_scanner, "_run_json", lambda cmd: {"dependencies": []} if cmd[0] == "pip-audit" else [])

    outcome = python_scanner.scan_python(tmp_path)

    assert outcome.findings == ()
    assert outcome.notices == ()


def test_scan_python_reports_notice_on_malformed_output(tmp_path, monkeypatch):
    monkeypatch.setattr(python_scanner.shutil, "which", lambda name: "/usr/bin/pip-audit")
    monkeypatch.setattr(python_scanner, "_run_json", lambda cmd: None)

    outcome = python_scanner.scan_python(tmp_path)

    assert outcome.findings == ()
    assert len(outcome.notices) == 2
