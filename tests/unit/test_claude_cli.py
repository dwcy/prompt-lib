"""Unit tests for cabal.claude_cli launcher resolution.

Regression coverage for the Windows `.cmd` shim bug: `subprocess` (shell=False)
does not honour PATHEXT, so a bare "claude" argv fails to launch the `.cmd`
shim. `_claude_exe()` must resolve the full path via `shutil.which`.
"""

from __future__ import annotations

import cabal.claude_cli as c


def test_claude_exe_returns_resolved_path_from_which(monkeypatch):
    c._claude_exe.cache_clear()
    monkeypatch.setattr(c.shutil, "which", lambda name: r"C:\npm\claude.CMD")

    assert c._claude_exe() == r"C:\npm\claude.CMD"


def test_claude_exe_falls_back_to_bare_name_when_not_found(monkeypatch):
    c._claude_exe.cache_clear()
    monkeypatch.setattr(c.shutil, "which", lambda name: None)

    assert c._claude_exe() == "claude"


def test_run_claude_cli_launches_resolved_executable(monkeypatch):
    c._claude_exe.cache_clear()
    monkeypatch.setattr(c.shutil, "which", lambda name: r"C:\npm\claude.CMD")
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv

        class _R:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return _R()

    monkeypatch.setattr(c.subprocess, "run", fake_run)

    c._run_claude_cli(["mcp", "list"])

    assert captured["argv"] == [r"C:\npm\claude.CMD", "mcp", "list"]
