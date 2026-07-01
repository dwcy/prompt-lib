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
    assert calls == [["winget", "install", "--id=astral-sh.uv", *uv._WINGET_FLAGS]]


def test_ensure_uv_tool_bin_prepends_missing_dir(monkeypatch):
    from pathlib import Path

    bin_dir = Path("/opt/uv-bin")
    monkeypatch.setattr(uv, "uv_tool_bin_dir", lambda: bin_dir)
    monkeypatch.setenv("PATH", uv.os.pathsep.join(["/usr/bin", "/bin"]))

    uv.ensure_uv_tool_bin_on_path()

    parts = uv.os.environ["PATH"].split(uv.os.pathsep)
    assert parts[0] == str(bin_dir)
    assert "/usr/bin" in parts


def test_ensure_uv_tool_bin_is_idempotent(monkeypatch):
    from pathlib import Path

    bin_dir = Path("/opt/uv-bin")
    monkeypatch.setattr(uv, "uv_tool_bin_dir", lambda: bin_dir)
    monkeypatch.setenv("PATH", uv.os.pathsep.join([str(bin_dir), "/usr/bin"]))

    uv.ensure_uv_tool_bin_on_path()

    assert uv.os.environ["PATH"].split(uv.os.pathsep).count(str(bin_dir)) == 1
