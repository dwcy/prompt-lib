# -*- coding: utf-8 -*-
"""Unit tests for the .NET package security scanner — no real `dotnet` invocation."""

from __future__ import annotations

import json
import subprocess

import pytest

from cabal.package_security import dotnet_scanner


class _FakeCompletedProcess:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode


def _vulnerable_json(project_path: str) -> str:
    return json.dumps(
        {
            "projects": [
                {
                    "path": project_path,
                    "frameworks": [
                        {
                            "topLevelPackages": [
                                {
                                    "id": "Newtonsoft.Json",
                                    "requestedVersion": "12.0.1",
                                    "resolvedVersion": "12.0.1",
                                    "vulnerabilities": [
                                        {
                                            "severity": "High",
                                            "advisoryurl": "https://example.test/advisory",
                                        }
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }
    )


def _outdated_json(project_path: str) -> str:
    return json.dumps(
        {
            "projects": [
                {
                    "path": project_path,
                    "frameworks": [
                        {
                            "topLevelPackages": [
                                {
                                    "id": "Newtonsoft.Json",
                                    "requestedVersion": "12.0.1",
                                    "resolvedVersion": "12.0.1",
                                    "latestVersion": "13.0.4",
                                }
                            ]
                        }
                    ],
                }
            ]
        }
    )


def _deprecated_json(project_path: str) -> str:
    return json.dumps(
        {
            "projects": [
                {
                    "path": project_path,
                    "frameworks": [
                        {
                            "topLevelPackages": [
                                {
                                    "id": "Old.Package",
                                    "requestedVersion": "1.0.0",
                                    "resolvedVersion": "1.0.0",
                                    "deprecationReasons": ["Legacy"],
                                    "alternativePackage": {
                                        "id": "New.Package",
                                        "versionRange": "[2.0.0, )",
                                    },
                                }
                            ]
                        }
                    ],
                }
            ]
        }
    )


def _fake_run_for(project_path: str):
    def _fake_run(cmd, **kwargs):
        if "--vulnerable" in cmd:
            return _FakeCompletedProcess(_vulnerable_json(project_path))
        if "--outdated" in cmd:
            return _FakeCompletedProcess(_outdated_json(project_path))
        if "--deprecated" in cmd:
            return _FakeCompletedProcess(_deprecated_json(project_path))
        raise AssertionError(f"unexpected dotnet invocation: {cmd}")

    return _fake_run


@pytest.fixture(autouse=True)
def _fake_dotnet_binary(monkeypatch):
    monkeypatch.setattr(dotnet_scanner.shutil, "which", lambda name: "/usr/bin/dotnet")


def test_scan_dotnet_reports_notice_when_cli_missing(tmp_path, monkeypatch):
    (tmp_path / "app.csproj").write_text("<Project />", encoding="utf-8")
    monkeypatch.setattr(dotnet_scanner.shutil, "which", lambda name: None)

    outcome = dotnet_scanner.scan_dotnet(tmp_path)

    assert outcome.findings == ()
    assert "dotnet CLI not found" in outcome.notices[0]


def test_scan_dotnet_returns_no_findings_without_project_files(tmp_path):
    outcome = dotnet_scanner.scan_dotnet(tmp_path)

    assert outcome.findings == ()
    assert outcome.notices == ()


def test_scan_dotnet_parses_vulnerable_outdated_and_deprecated(tmp_path, monkeypatch):
    csproj = tmp_path / "app.csproj"
    csproj.write_text("<Project />", encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", _fake_run_for(str(csproj)))

    outcome = dotnet_scanner.scan_dotnet(tmp_path)
    by_kind = {f.kind: f for f in outcome.findings}

    assert by_kind["vulnerable"].package == "Newtonsoft.Json"
    assert by_kind["vulnerable"].severity == "High"
    assert by_kind["outdated"].target_version == "13.0.4"
    assert by_kind["outdated"].fix_command == f'dotnet add "{csproj}" package Newtonsoft.Json --version 13.0.4'
    assert by_kind["deprecated"].package == "Old.Package"
    assert by_kind["deprecated"].fix_command is None


def test_scan_dotnet_adds_notice_on_malformed_json(tmp_path, monkeypatch):
    (tmp_path / "app.csproj").write_text("<Project />", encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kwargs: _FakeCompletedProcess("not json"))

    outcome = dotnet_scanner.scan_dotnet(tmp_path)

    assert outcome.findings == ()
    assert len(outcome.notices) == 3
