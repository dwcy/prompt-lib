# -*- coding: utf-8 -*-
"""Unit tests for Package Security Check orchestration: detection, caching, fixing."""

from __future__ import annotations

import pytest

from cabal import widget_cache
from cabal.package_security import service
from cabal.package_security.models import Finding, ScanOutcome


@pytest.fixture(autouse=True)
def _isolated_cache_file(tmp_path, monkeypatch):
    """Redirect widget_cache's module-level file constants into a throwaway dir."""
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", tmp_path / "cache-root")
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", tmp_path / "cache-root" / "cache.json")


def test_detect_ecosystems_finds_dotnet_from_root_csproj(tmp_path):
    (tmp_path / "app.csproj").write_text("<Project />", encoding="utf-8")

    assert service.detect_ecosystems(tmp_path) == ["dotnet"]


def test_detect_ecosystems_finds_dotnet_from_nested_csproj(tmp_path):
    nested = tmp_path / "src" / "App"
    nested.mkdir(parents=True)
    (nested / "App.csproj").write_text("<Project />", encoding="utf-8")

    assert service.detect_ecosystems(tmp_path) == ["dotnet"]


def test_detect_ecosystems_finds_npm_from_package_json(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    assert service.detect_ecosystems(tmp_path) == ["npm"]


def test_detect_ecosystems_finds_python_from_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")

    assert service.detect_ecosystems(tmp_path) == ["python"]


def test_detect_ecosystems_returns_empty_for_project_with_no_markers(tmp_path):
    assert service.detect_ecosystems(tmp_path) == []


def test_detect_ecosystems_combines_all_present_ecosystems_in_fixed_order(tmp_path):
    (tmp_path / "app.csproj").write_text("<Project />", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")

    assert service.detect_ecosystems(tmp_path) == ["dotnet", "npm", "python"]


def test_scan_project_only_dispatches_detected_ecosystem_scanners(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setitem(
        service._SCANNERS, "npm", lambda p: calls.append("npm") or ScanOutcome("npm", ())
    )
    monkeypatch.setitem(
        service._SCANNERS,
        "dotnet",
        lambda p: calls.append("dotnet") or ScanOutcome("dotnet", ()),
    )

    service.scan_project(tmp_path)

    assert calls == ["npm"]


def test_cache_round_trip_preserves_finding_fields(tmp_path):
    finding = Finding(
        ecosystem="npm",
        package="lodash",
        kind="vulnerable",
        severity="high",
        current_version="4.17.15",
        target_version="4.17.21",
        fix_command="npm install lodash@4.17.21",
        detail="Prototype Pollution",
    )
    outcomes = [ScanOutcome(ecosystem="npm", findings=(finding,), notices=("a notice",))]

    service.save_cache(tmp_path, outcomes)
    loaded = service.load_cached(tmp_path)

    assert loaded == outcomes


def test_cache_is_scoped_per_project_path(tmp_path):
    project_a = tmp_path / "a"
    project_b = tmp_path / "b"
    project_a.mkdir()
    project_b.mkdir()
    service.save_cache(project_a, [ScanOutcome(ecosystem="npm", findings=())])

    assert service.load_cached(project_b) is None


def test_load_cached_returns_none_before_any_scan(tmp_path):
    assert service.load_cached(tmp_path) is None


def test_apply_fix_without_fix_command_does_not_run_anything(tmp_path, monkeypatch):
    finding = Finding("npm", "lodash", "deprecated", "info", "1.0.0", None, None)
    monkeypatch.setattr(
        service.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError())
    )

    ok, message = service.apply_fix(finding, tmp_path)

    assert ok is False


def test_apply_fix_reports_success_on_zero_exit(tmp_path, monkeypatch):
    finding = Finding("npm", "lodash", "outdated", "info", "4.0.0", "5.0.0", "npm install lodash@5.0.0")

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(service.subprocess, "run", lambda *a, **k: _Result())

    ok, message = service.apply_fix(finding, tmp_path)

    assert ok is True


def test_apply_fix_reports_failure_and_stderr_on_nonzero_exit(tmp_path, monkeypatch):
    finding = Finding("npm", "lodash", "outdated", "info", "4.0.0", "5.0.0", "npm install lodash@5.0.0")

    class _Result:
        returncode = 1
        stdout = ""
        stderr = "network error"

    monkeypatch.setattr(service.subprocess, "run", lambda *a, **k: _Result())

    ok, message = service.apply_fix(finding, tmp_path)

    assert ok is False and "network error" in message
