"""Unit tests for the repo-local service installers (a2a_bridge, orchestrator) — T019.

Covers the C4 installer guarantees: uv-missing yields an actionable (False, msg);
status reflects PATH presence; the install success path returns (True, msg). Every
test is hermetic — shutil.which, subprocess.run, and uv_install are monkeypatched in
the installer module so no real uv/subprocess/network call happens.
"""

from __future__ import annotations

import types

import pytest

from cabal.installers import a2a_bridge, orchestrator

INSTALLERS = (
    pytest.param(a2a_bridge, "a2a-bridge", id="a2a_bridge"),
    pytest.param(orchestrator, "orchestrator", id="orchestrator"),
)


def _install_fn(module: types.ModuleType):
    return getattr(module, f"{module.__name__.rsplit('.', 1)[-1]}_install")


def _status_fn(module: types.ModuleType):
    return getattr(module, f"{module.__name__.rsplit('.', 1)[-1]}_status")


def _patch_which(
    monkeypatch: pytest.MonkeyPatch,
    module: types.ModuleType,
    mapping: dict[str, str | None],
) -> None:
    monkeypatch.setattr(module.shutil, "which", lambda name: mapping.get(name))


def _forbid_subprocess(
    monkeypatch: pytest.MonkeyPatch, module: types.ModuleType
) -> None:
    def _boom(*_args, **_kwargs):
        raise AssertionError("subprocess.run must not be called in this test")

    monkeypatch.setattr(module.subprocess, "run", _boom)


@pytest.mark.parametrize("module, console", INSTALLERS)
def test_install_uv_missing_and_unprovisionable_returns_actionable_failure(
    monkeypatch: pytest.MonkeyPatch, module: types.ModuleType, console: str
) -> None:
    _patch_which(monkeypatch, module, {"uv": None, console: None})
    monkeypatch.setattr(module, "uv_install", lambda: (False, "no installer"))
    _forbid_subprocess(monkeypatch, module)

    ok, msg = _install_fn(module)()

    assert ok is False
    assert "uv" in msg
    assert msg.strip()


@pytest.mark.parametrize("module, console", INSTALLERS)
def test_install_uv_autoinstalled_but_still_off_path_returns_actionable_failure(
    monkeypatch: pytest.MonkeyPatch, module: types.ModuleType, console: str
) -> None:
    _patch_which(monkeypatch, module, {"uv": None, console: None})
    monkeypatch.setattr(module, "uv_install", lambda: (True, "installed uv"))
    _forbid_subprocess(monkeypatch, module)

    ok, msg = _install_fn(module)()

    assert ok is False
    assert "uv" in msg


@pytest.mark.parametrize("module, console", INSTALLERS)
def test_status_returns_true_when_console_on_path(
    monkeypatch: pytest.MonkeyPatch, module: types.ModuleType, console: str
) -> None:
    _patch_which(monkeypatch, module, {console: f"/usr/local/bin/{console}"})

    set_up, detail = _status_fn(module)()

    assert set_up is True
    assert isinstance(detail, str) and detail.strip()


@pytest.mark.parametrize("module, console", INSTALLERS)
def test_status_returns_false_when_console_absent(
    monkeypatch: pytest.MonkeyPatch, module: types.ModuleType, console: str
) -> None:
    _patch_which(monkeypatch, module, {console: None})

    set_up, detail = _status_fn(module)()

    assert set_up is False
    assert isinstance(detail, str) and detail.strip()


@pytest.mark.parametrize("module, console", INSTALLERS)
def test_install_fresh_success_returns_true(
    monkeypatch: pytest.MonkeyPatch, module: types.ModuleType, console: str
) -> None:
    _patch_which(monkeypatch, module, {"uv": "/usr/bin/uv", console: None})
    monkeypatch.setattr(
        module,
        "uv_install",
        lambda: pytest.fail("uv_install must not run when uv is present"),
    )
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="done", stderr=""),
    )

    ok, msg = _install_fn(module)()

    assert ok is True
    assert isinstance(msg, str) and msg.strip()


@pytest.mark.parametrize("module, console", INSTALLERS)
def test_install_force_clean_rebuild_from_local_checkout(
    monkeypatch: pytest.MonkeyPatch, module: types.ModuleType, console: str
) -> None:
    # Local checkout, console already present: must force a clean, uncached rebuild
    # (not a no-op `uv tool upgrade`) so local code changes always reinstall.
    _patch_which(
        monkeypatch, module, {"uv": "/usr/bin/uv", console: f"/usr/bin/{console}"}
    )
    monkeypatch.setattr(module, "_resolve_source", lambda: ("/local/checkout", True))
    captured: dict[str, list[str]] = {}

    def _run(cmd, *a, **k):
        captured["cmd"] = cmd
        return types.SimpleNamespace(returncode=0, stdout="reinstalled", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _run)

    ok, _msg = _install_fn(module)()

    cmd = captured["cmd"]
    assert ok is True
    assert "install" in cmd and "upgrade" not in cmd
    assert "--reinstall" in cmd
    assert "--no-cache" in cmd


@pytest.mark.parametrize("module, console", INSTALLERS)
def test_install_git_fallback_keeps_the_cache(
    monkeypatch: pytest.MonkeyPatch, module: types.ModuleType, console: str
) -> None:
    # No local checkout (git subdirectory source): force reinstall but keep the
    # cache — no --no-cache/--reinstall churn for the non-dev path.
    _patch_which(monkeypatch, module, {"uv": "/usr/bin/uv", console: None})
    monkeypatch.setattr(
        module, "_resolve_source", lambda: ("git+https://x#subdirectory=y", False)
    )
    captured: dict[str, list[str]] = {}

    def _run(cmd, *a, **k):
        captured["cmd"] = cmd
        return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _run)

    ok, _msg = _install_fn(module)()

    cmd = captured["cmd"]
    assert ok is True
    assert "--force" in cmd
    assert "--no-cache" not in cmd
    assert "--reinstall" not in cmd


@pytest.mark.parametrize("module, console", INSTALLERS)
def test_install_nonzero_returncode_returns_failure(
    monkeypatch: pytest.MonkeyPatch, module: types.ModuleType, console: str
) -> None:
    _patch_which(monkeypatch, module, {"uv": "/usr/bin/uv", console: None})
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *a, **k: types.SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )

    ok, _msg = _install_fn(module)()

    assert ok is False
