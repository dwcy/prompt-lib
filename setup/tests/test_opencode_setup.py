# -*- coding: utf-8 -*-
"""Tests for OpenCode setup helpers."""

from __future__ import annotations

import json

from cabal.installers import ai_clis
from cabal.opencode_setup import conversion, status
from cabal.opencode_setup.paths import OPENCODE_SOURCE_DIR


def _write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_opencode_global_plan_applies_config_tools_and_skills(tmp_path, monkeypatch):
    source = tmp_path / "global" / "opencode"
    codex = tmp_path / "global" / "codex"
    target = tmp_path / "opencode-target"
    monkeypatch.setattr(conversion, "OPENCODE_SOURCE_DIR", source)
    monkeypatch.setattr(conversion, "CODEX_SOURCE_DIR", codex)

    _write(
        source / "opencode.json",
        json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "mcp": {"codex": {"type": "local", "command": ["codex", "mcp-server"]}},
            }
        ),
    )
    _write(source / "tui.json", '{"$schema":"https://opencode.ai/tui.json"}')
    _write(source / "tools" / "claude-ask.ts", "export default {}")
    _write(codex / "skills" / "demo" / "SKILL.md", "---\nname: demo\ndescription: Demo\n---\n")
    _write(target / "opencode.json", '{"model":"opencode/gpt-5.1-codex"}')

    assets = conversion.build_global_plan(target)

    assert {asset.label for asset in assets} >= {
        "opencode.json",
        "tui.json",
        "tools/claude-ask.ts",
        "skills/demo/SKILL.md",
    }

    copied, skipped = conversion.apply_assets(assets)

    assert copied == 4
    assert skipped == 0
    merged = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
    assert merged["model"] == "opencode/gpt-5.1-codex"
    assert merged["mcp"]["codex"]["command"] == ["codex", "mcp-server"]
    assert (target / "skills" / "demo" / "SKILL.md").is_file()
    assert (target / "tools" / "claude-ask.ts").is_file()


def test_opencode_project_plan_targets_project_root_config(tmp_path, monkeypatch):
    source = tmp_path / "global" / "opencode"
    codex = tmp_path / "global" / "codex"
    project = tmp_path / "project"
    monkeypatch.setattr(conversion, "OPENCODE_SOURCE_DIR", source)
    monkeypatch.setattr(conversion, "CODEX_SOURCE_DIR", codex)

    _write(source / "opencode.json", '{"$schema":"https://opencode.ai/config.json"}')
    _write(source / "tools" / "gemini-ask.ts", "export default {}")
    _write(codex / "skills" / "demo" / "SKILL.md", "---\nname: demo\ndescription: Demo\n---\n")

    assets = conversion.build_project_plan(project)

    targets = {asset.target.relative_to(project).as_posix() for asset in assets}
    assert "opencode.json" in targets
    assert ".opencode/tools/gemini-ask.ts" in targets
    assert ".opencode/skills/demo/SKILL.md" in targets


def test_codex_mcp_status_reads_opencode_config(tmp_path):
    _write(
        tmp_path / "opencode.json",
        json.dumps({"mcp": {"codex": {"type": "local", "command": ["codex", "mcp-server"]}}}),
    )

    assert status.codex_mcp_configured(tmp_path) is True


def test_opencode_desktop_windows_install_uses_official_download(monkeypatch, tmp_path):
    calls: dict[str, object] = {}
    installer = tmp_path / "opencode-desktop-setup.exe"

    def fake_download(url: str, filename: str):
        calls["download"] = (url, filename)
        return installer, "downloaded"

    def fake_launch(path):
        calls["launch"] = path
        return True, "launched"

    monkeypatch.setattr(ai_clis.platform, "system", lambda: "Windows")
    monkeypatch.setattr(ai_clis.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(ai_clis, "_download_opencode_desktop", fake_download)
    monkeypatch.setattr(ai_clis, "_launch_windows_installer", fake_launch)

    ok, msg = ai_clis.opencode_desktop_install()

    assert ok is True
    assert "downloaded" in msg
    assert calls["download"] == (
        "https://opencode.ai/download/stable/windows-x64-nsis",
        "opencode-desktop-setup.exe",
    )
    assert calls["launch"] == installer


def test_bundled_opencode_assets_match_contract():
    config = json.loads((OPENCODE_SOURCE_DIR / "opencode.json").read_text(encoding="utf-8"))

    assert config["$schema"] == "https://opencode.ai/config.json"
    assert config["mcp"]["codex"]["type"] == "local"
    assert config["mcp"]["codex"]["command"][-1] == "mcp-server"
    assert config["permission"]["codex_*"] == "ask"

    for tool_name in ("claude-ask.ts", "gemini-ask.ts", "antigravity-chat.ts"):
        text = (OPENCODE_SOURCE_DIR / "tools" / tool_name).read_text(encoding="utf-8")
        assert 'from "@opencode-ai/plugin"' in text
        assert "export default tool" in text
