# -*- coding: utf-8 -*-
"""Round-trip tests for the inject-email git filter (setup/tools/email-filter.py)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

FILTER_PATH = Path(__file__).resolve().parents[1] / "tools" / "email-filter.py"

spec = importlib.util.spec_from_file_location("email_filter", FILTER_PATH)
email_filter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(email_filter)

MANIFEST = '{\n  "author": {\n    "email": "%s"\n  }\n}\n'


def test_smudge_injects_logged_in_email(monkeypatch):
    monkeypatch.setattr(email_filter, "logged_in_email", lambda: "me@test.dev")
    out = email_filter.smudge(MANIFEST % email_filter.PLACEHOLDER)
    assert out == MANIFEST % "me@test.dev"


def test_clean_strips_logged_in_email(monkeypatch):
    monkeypatch.setattr(email_filter, "logged_in_email", lambda: "me@test.dev")
    out = email_filter.clean(MANIFEST % "me@test.dev")
    assert out == MANIFEST % email_filter.PLACEHOLDER


def test_round_trip_is_stable(monkeypatch):
    monkeypatch.setattr(email_filter, "logged_in_email", lambda: "me@test.dev")
    committed = MANIFEST % email_filter.PLACEHOLDER
    assert email_filter.clean(email_filter.smudge(committed)) == committed


def test_no_login_passes_through(monkeypatch):
    monkeypatch.setattr(email_filter, "logged_in_email", lambda: None)
    committed = MANIFEST % email_filter.PLACEHOLDER
    assert email_filter.smudge(committed) == committed
    assert email_filter.clean(committed) == committed
