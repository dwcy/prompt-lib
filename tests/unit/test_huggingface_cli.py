"""Hugging Face CLI install and detection tests."""

from __future__ import annotations

from cabal import env_detect
from cabal.installers import ai_clis


def test_huggingface_install_uses_homebrew_when_available(monkeypatch):
    calls: list[list[str]] = []

    monkeypatch.setattr(ai_clis.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        ai_clis.shutil,
        "which",
        lambda name: "/opt/homebrew/bin/brew" if name == "brew" else None,
    )
    monkeypatch.setattr(
        ai_clis,
        "_run_install",
        lambda cmd: (calls.append(cmd), (True, "ok"))[1],
    )

    ok, _message = ai_clis.huggingface_install()

    assert ok is True
    assert calls == [["brew", "install", "hf"]]


def test_huggingface_install_uses_uv_tool_package(monkeypatch):
    calls: list[list[str]] = []

    monkeypatch.setattr(ai_clis.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        ai_clis.shutil,
        "which",
        lambda name: "uv.exe" if name == "uv" else None,
    )
    monkeypatch.setattr(
        ai_clis,
        "_run_install",
        lambda cmd: (calls.append(cmd), (True, "ok"))[1],
    )

    ok, _message = ai_clis.huggingface_install()

    assert ok is True
    assert calls == [["uv", "tool", "install", "hf"]]


def test_huggingface_install_falls_back_to_huggingface_hub(monkeypatch):
    calls: list[list[str]] = []

    monkeypatch.setattr(ai_clis.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        ai_clis.shutil,
        "which",
        lambda name: "python.exe" if name == "python" else None,
    )
    monkeypatch.setattr(
        ai_clis,
        "_run_install",
        lambda cmd: (calls.append(cmd), (True, "ok"))[1],
    )

    ok, _message = ai_clis.huggingface_install()

    assert ok is True
    assert calls == [
        ["python", "-m", "pip", "install", "--user", "huggingface_hub"]
    ]


def test_huggingface_detection_uses_current_hf_binary(monkeypatch):
    monkeypatch.setattr(
        env_detect.shutil,
        "which",
        lambda name: "huggingface-cli.exe" if name == "huggingface-cli" else None,
    )

    assert env_detect._has_huggingface_cli() is False

    monkeypatch.setattr(
        env_detect.shutil,
        "which",
        lambda name: "hf.exe" if name == "hf" else None,
    )

    assert env_detect._has_huggingface_cli() is True
