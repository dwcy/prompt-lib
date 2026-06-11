# -*- coding: utf-8 -*-
"""Round-trip tests for the inject-email git filter (setup/tools/email-filter.py)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

FILTER_PATH = Path(__file__).resolve().parents[1] / "tools" / "email-filter.py"

spec = importlib.util.spec_from_file_location("email_filter", FILTER_PATH)
email_filter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(email_filter)

MANIFEST = (
    '{\n  "author": {\n    "name": "%s",\n    "email": "%s"\n  },\n'
    '  "homepage": "%s"\n}\n'
)


def _patch_identity(
    monkeypatch, email="me@test.dev", name="Test User", url="https://github.com/me/repo"
):
    monkeypatch.setattr(email_filter, "logged_in_email", lambda: email)
    monkeypatch.setattr(email_filter, "git_user_name", lambda: name)
    monkeypatch.setattr(email_filter, "repo_url", lambda: url)


def _placeholders() -> tuple[str, str, str]:
    return (
        email_filter.NAME_PLACEHOLDER,
        email_filter.EMAIL_PLACEHOLDER,
        email_filter.REPO_PLACEHOLDER,
    )


def test_smudge_injects_all_identity_values(monkeypatch):
    _patch_identity(monkeypatch)

    out = email_filter.smudge(MANIFEST % _placeholders())

    assert out == MANIFEST % ("Test User", "me@test.dev", "https://github.com/me/repo")


def test_clean_strips_all_identity_values(monkeypatch):
    _patch_identity(monkeypatch)

    out = email_filter.clean(
        MANIFEST % ("Test User", "me@test.dev", "https://github.com/me/repo")
    )

    assert out == MANIFEST % _placeholders()


def test_round_trip_is_stable(monkeypatch):
    _patch_identity(monkeypatch)
    committed = MANIFEST % _placeholders()

    assert email_filter.clean(email_filter.smudge(committed)) == committed


def test_unresolvable_values_pass_through(monkeypatch):
    _patch_identity(monkeypatch, email=None, name=None, url=None)
    committed = MANIFEST % _placeholders()

    assert email_filter.smudge(committed) == committed
    assert email_filter.clean(committed) == committed


def test_partial_identity_substitutes_only_resolved(monkeypatch):
    _patch_identity(monkeypatch, name=None, url=None)

    out = email_filter.smudge(MANIFEST % _placeholders())

    assert out == MANIFEST % (
        email_filter.NAME_PLACEHOLDER,
        "me@test.dev",
        email_filter.REPO_PLACEHOLDER,
    )


def test_repo_url_normalises_ssh_remote(monkeypatch):
    def fake_run(*args, **kwargs):
        class R:
            returncode = 0
            stdout = "git@github.com:me/repo.git\n"

        return R()

    monkeypatch.setattr(email_filter.subprocess, "run", fake_run)

    assert email_filter.repo_url() == "https://github.com/me/repo"


def test_repo_url_strips_dot_git_from_https(monkeypatch):
    def fake_run(*args, **kwargs):
        class R:
            returncode = 0
            stdout = "https://github.com/me/repo.git\n"

        return R()

    monkeypatch.setattr(email_filter.subprocess, "run", fake_run)

    assert email_filter.repo_url() == "https://github.com/me/repo"
