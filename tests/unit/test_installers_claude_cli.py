"""Unit tests for cabal.installers.claude_cli status probe.

Regression coverage for the Windows `.cmd` shim bug: the status probe must
launch the path resolved by `shutil.which` (with extension), not a bare
"claude" argv that CreateProcess cannot find.
"""

from __future__ import annotations

import cabal.installers.claude_cli as c


def test_claude_cli_status_not_installed_when_which_returns_none(monkeypatch):
    monkeypatch.setattr(c.shutil, "which", lambda name: None)

    assert c.claude_cli_status() == "not installed"


def test_claude_cli_status_launches_resolved_executable(monkeypatch):
    monkeypatch.setattr(c.shutil, "which", lambda name: r"C:\npm\claude.CMD")
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv

        class _R:
            returncode = 0
            stdout = "1.2.3 (Claude Code)"
            stderr = ""

        return _R()

    monkeypatch.setattr(c.subprocess, "run", fake_run)

    result = c.claude_cli_status()

    assert captured["argv"] == [r"C:\npm\claude.CMD", "--version"]
    assert result == "installed 1.2.3 (Claude Code)"


def test_claude_cli_status_survives_launch_failure(monkeypatch):
    monkeypatch.setattr(c.shutil, "which", lambda name: r"C:\npm\claude.CMD")

    def boom(argv, **kwargs):
        raise OSError("CreateProcess failed")

    monkeypatch.setattr(c.subprocess, "run", boom)

    assert c.claude_cli_status() == "installed"
