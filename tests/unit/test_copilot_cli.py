"""GitHub Copilot CLI install and detection tests."""

from __future__ import annotations

from cabal import env_detect
from cabal.installers import ai_clis


def test_copilot_install_uses_current_windows_winget_package(monkeypatch):
    calls: list[list[str]] = []

    monkeypatch.setattr(ai_clis.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        ai_clis.shutil,
        "which",
        lambda name: "winget.exe" if name == "winget" else None,
    )
    monkeypatch.setattr(
        ai_clis,
        "_run_install",
        lambda cmd: (calls.append(cmd), (True, "ok"))[1],
    )

    ok, _message = ai_clis.copilot_install()

    assert ok is True
    assert calls == [
        [
            "winget",
            "install",
            "--id",
            "GitHub.Copilot",
            *ai_clis._WINGET_FLAGS,
        ]
    ]


def test_copilot_install_uses_brew_package_on_unix(monkeypatch):
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

    ok, _message = ai_clis.copilot_install()

    assert ok is True
    assert calls == [["brew", "install", "copilot-cli"]]


def test_copilot_install_falls_back_to_official_npm_package(monkeypatch):
    packages: list[str] = []

    monkeypatch.setattr(ai_clis.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        ai_clis.shutil,
        "which",
        lambda name: "/usr/bin/npm" if name == "npm" else None,
    )
    monkeypatch.setattr(
        ai_clis,
        "_npm_global_install",
        lambda package: (packages.append(package), (True, "ok"))[1],
    )

    ok, _message = ai_clis.copilot_install()

    assert ok is True
    assert packages == ["@github/copilot"]


def test_copilot_detection_ignores_legacy_gh_extension_binary(monkeypatch):
    monkeypatch.setattr(
        env_detect.shutil,
        "which",
        lambda name: "gh-copilot.exe" if name == "gh-copilot" else None,
    )

    assert env_detect._has_copilot_cli() is False

    monkeypatch.setattr(
        env_detect.shutil,
        "which",
        lambda name: "copilot.exe" if name == "copilot" else None,
    )

    assert env_detect._has_copilot_cli() is True
