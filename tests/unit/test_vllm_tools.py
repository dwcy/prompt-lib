"""vLLM registry and platform-guard tests."""

from __future__ import annotations

from cabal import tools
from cabal.installers import ai_clis


def test_vllm_is_registered_as_local_ai_tool():
    local_ai = dict(tools.ENV_TOOL_GROUPS)["Local AI"]
    installers = {key for key, _label, _fn in tools.ENV_INSTALLERS}

    assert "vllm" in local_ai
    assert "vllm" in installers


def test_vllm_unavailable_reason_is_non_linux_only(monkeypatch):
    monkeypatch.setattr(tools.platform, "system", lambda: "Windows")

    assert "Linux only" in (tools._tool_unavailable_reason("vllm") or "")

    monkeypatch.setattr(tools.platform, "system", lambda: "Linux")

    assert tools._tool_unavailable_reason("vllm") is None


def test_vllm_installer_blocks_non_linux(monkeypatch):
    monkeypatch.setattr(ai_clis.platform, "system", lambda: "Darwin")

    ok, msg = ai_clis.vllm_install()

    assert ok is False
    assert "Linux" in msg
    assert "WSL2" in msg
