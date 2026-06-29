"""Unit tests for the env-summary version formatters (git / uv cleanup)."""

from __future__ import annotations

import pytest

from cabal.env_summary import _short_git_version, _short_uv_version


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("git version 2.43.0.windows.1", "2.43.0"),
        ("git version 2.39.5", "2.39.5"),
        ("", None),
        (None, None),
    ],
)
def test_short_git_version_extracts_semver(raw, expected):
    assert _short_git_version(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("uv 0.5.1 (abc1234 2024-01-01)", "0.5.1"),
        ("uv 0.4.30", "0.4.30"),
        ("", None),
        (None, None),
    ],
)
def test_short_uv_version_extracts_semver(raw, expected):
    assert _short_uv_version(raw) == expected


def test_short_version_falls_back_to_raw_when_no_semver():
    assert _short_git_version("git installed") == "git installed"
