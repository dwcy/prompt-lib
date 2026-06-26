"""uv installer tests."""

from __future__ import annotations

from cabal.installers import uv


def test_uv_windows_install_uses_astral_winget_id(monkeypatch):
    calls: list[list[str]] = []

    monkeypatch.setattr(uv.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        uv.shutil,
        "which",
        lambda name: "winget.exe" if name == "winget" else None,
    )
    monkeypatch.setattr(
        uv,
        "_run_install",
        lambda cmd: (calls.append(cmd), (True, "ok"))[1],
    )

    ok, _message = uv.uv_install()

    assert ok is True
    assert calls == [
        ["winget", "install", "--id=astral-sh.uv", *uv._WINGET_FLAGS]
    ]
