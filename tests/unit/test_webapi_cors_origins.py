"""Regression tests: the Vite dev origins must not ship in packaged builds."""

from __future__ import annotations

import pytest

from cabal.webapi.security import DEV_ORIGINS, TAURI_ORIGINS, allowed_origins


def test_packaged_build_allows_only_the_tauri_origins() -> None:
    origins = allowed_origins(dev=False)

    assert origins == list(TAURI_ORIGINS)


def test_dev_mode_additionally_allows_the_vite_origins() -> None:
    origins = allowed_origins(dev=True)

    assert set(DEV_ORIGINS).issubset(origins)


def test_dev_origins_are_absent_when_the_dev_env_var_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CABAL_DEV", raising=False)

    origins = allowed_origins()

    assert not set(DEV_ORIGINS).intersection(origins)
