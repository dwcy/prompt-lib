"""Integration tests for ClaudeStatsPanel (T088).

Exercises parse_status, read_claude_dot_json_fallback, and the panel's _render
method directly — no Textual driver, no async pilot. Token-leak guarantees are
enforced via dataclass field whitelist and rendered-output regex checks.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

from cabal.widgets.claude_stats_panel import (
    ClaudeAccountStatus,
    ClaudeStatsPanel,
    parse_status,
    read_claude_dot_json_fallback,
)


_FULL_FIXTURE = """\
Claude Code v1.2.3
Account: pawzor@gmail.com (Max 20x)
Active model: claude-opus-4-7
5-hour message usage: 42%
Weekly cap: 18%
Session: signed in
"""

_PRO_FIXTURE = """\
Claude Code v1.2.3
Account: x@y.com (Pro)
Active model: claude-sonnet-4-5
"""

_MAX_5X_FIXTURE = "Account: a@b.io (Max 5x)\n"
_MAX_20X_FIXTURE = "Account: a@b.io (Max 20x)\n"


def test_parse_status_full_happy_path():
    st = parse_status(_FULL_FIXTURE)

    assert st.email == "pawzor@gmail.com"
    assert st.account_type == "Max 20x"
    assert st.active_model == "claude-opus-4-7"
    assert st.five_hour_used_pct == 42
    assert st.weekly_cap_used_pct == 18
    assert st.signed_in is True
    assert st.raw_status_output is None


def test_parse_status_pro_account():
    st = parse_status(_PRO_FIXTURE)

    assert st.account_type == "Pro"


def test_parse_status_max_5x_vs_20x_ordering():
    st5 = parse_status(_MAX_5X_FIXTURE)
    st20 = parse_status(_MAX_20X_FIXTURE)

    assert st5.account_type == "Max 5x"
    assert st20.account_type == "Max 20x"


def test_parse_status_only_email_partial_parse():
    st = parse_status("Account: foo@bar.io (Pro)\n")

    assert st.email == "foo@bar.io"
    assert st.account_type == "Pro"
    assert st.active_model is None
    assert st.five_hour_used_pct is None
    assert st.weekly_cap_used_pct is None
    assert st.raw_status_output is None


def test_parse_status_garbage_populates_raw():
    st = parse_status("completely unrelated text\nfoo bar")

    assert st.account_type == "unknown"
    assert st.email is None
    assert st.raw_status_output is not None
    assert st.raw_status_output.strip().startswith("completely unrelated")


def test_parse_status_signed_in_from_text_only():
    st = parse_status("Session: signed in\n")

    assert st.signed_in is True


def test_fallback_reads_email_from_oauth_account(tmp_project_dir, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_project_dir))
    monkeypatch.setattr(Path, "home", lambda: tmp_project_dir)
    payload = {"oauthAccount": {"emailAddress": "alice@example.com", "organizationUuid": "abc-123"}}
    (tmp_project_dir / ".claude.json").write_text(json.dumps(payload), encoding="utf-8")

    st = read_claude_dot_json_fallback()

    assert st.email == "alice@example.com"
    assert st.signed_in is True
    assert st.token_present is True
    assert st.error == "claude CLI not installed"


def test_fallback_missing_file_returns_error_only(tmp_project_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_project_dir)

    st = read_claude_dot_json_fallback()

    assert st.email is None
    assert st.token_present is False
    assert st.error == "claude CLI not installed"


def test_fallback_corrupt_json_returns_error_only(tmp_project_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_project_dir)
    (tmp_project_dir / ".claude.json").write_text("garbage {", encoding="utf-8")

    st = read_claude_dot_json_fallback()

    assert st.email is None
    assert st.token_present is False
    assert st.error == "claude CLI not installed"


def test_status_dataclass_has_no_token_fields():
    allowed = {
        "account_type", "email", "signed_in", "five_hour_used_pct",
        "weekly_cap_used_pct", "active_model", "token_present",
        "raw_status_output", "error",
    }
    forbidden_substrings = ("apikey", "api_key", "secret", "password", "refresh")

    names = {f.name for f in dataclasses.fields(ClaudeAccountStatus)}

    assert names == allowed
    for name in names:
        lower = name.lower()
        if name == "token_present":
            continue
        assert "token" not in lower
        for sub in forbidden_substrings:
            assert sub not in lower


def test_render_dataclass_path_has_no_literal_tokens():
    st = ClaudeAccountStatus(
        account_type="Pro", email="a@b.com", signed_in=True,
        active_model="claude-opus-4-7", five_hour_used_pct=10,
        weekly_cap_used_pct=5, token_present=True,
    )
    panel = ClaudeStatsPanel()

    plain = str(panel._render(st))

    assert "a@b.com" in plain
    assert "Pro" in plain
    for needle in ("oauthToken", "accessToken", "apiKey", "refreshToken", "sk-"):
        assert needle not in plain
    assert not re.search(r"[0-9a-f]{32,}", plain, re.IGNORECASE)


def test_render_raw_output_path_shows_raw_verbatim():
    raw = "some weird /status output sk-fakeXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    st = ClaudeAccountStatus(raw_status_output=raw)
    panel = ClaudeStatsPanel()

    plain = str(panel._render(st))

    assert "sk-fakeXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX" in plain
