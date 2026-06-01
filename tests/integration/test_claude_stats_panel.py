"""Integration tests for ClaudeStatsPanel.

After the `claude -p /status` switch-out, plan/usage/model fields are gone —
they were never reliably populated since `-p` interprets `/status` as a prompt,
not a slash command. The panel now reads `~/.claude.json` only.
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
    read_claude_account_state,
)


def test_read_returns_email_from_oauth_account(tmp_project_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_project_dir)
    payload = {"oauthAccount": {"emailAddress": "alice@example.com", "organizationUuid": "abc-123"}}
    (tmp_project_dir / ".claude.json").write_text(json.dumps(payload), encoding="utf-8")

    st = read_claude_account_state()

    assert st.email == "alice@example.com"


def test_read_marks_signed_in_when_email_present(tmp_project_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_project_dir)
    payload = {"oauthAccount": {"emailAddress": "a@b.io", "organizationUuid": "x"}}
    (tmp_project_dir / ".claude.json").write_text(json.dumps(payload), encoding="utf-8")

    st = read_claude_account_state()

    assert st.signed_in is True


def test_read_marks_token_present_from_organization_uuid(tmp_project_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_project_dir)
    payload = {"oauthAccount": {"emailAddress": "a@b.io", "organizationUuid": "org-uuid"}}
    (tmp_project_dir / ".claude.json").write_text(json.dumps(payload), encoding="utf-8")

    st = read_claude_account_state()

    assert st.token_present is True


def test_read_missing_file_returns_error(tmp_project_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_project_dir)

    st = read_claude_account_state()

    assert st.email is None
    assert st.signed_in is False
    assert st.token_present is False
    assert "not found" in (st.error or "")


def test_read_corrupt_json_returns_error(tmp_project_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_project_dir)
    (tmp_project_dir / ".claude.json").write_text("garbage {", encoding="utf-8")

    st = read_claude_account_state()

    assert st.email is None
    assert st.token_present is False
    assert "could not be parsed" in (st.error or "")


def test_status_dataclass_field_whitelist():
    allowed = {"email", "signed_in", "token_present", "error"}
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


def test_render_does_not_leak_tokenlike_strings():
    st = ClaudeAccountStatus(email="a@b.com", signed_in=True, token_present=True)
    panel = ClaudeStatsPanel()

    plain = str(panel._render_body(st))

    assert "a@b.com" in plain
    for needle in ("oauthToken", "accessToken", "apiKey", "refreshToken", "sk-"):
        assert needle not in plain
    assert not re.search(r"[0-9a-f]{32,}", plain, re.IGNORECASE)


def test_render_signed_out_shows_login_hint():
    st = ClaudeAccountStatus()
    panel = ClaudeStatsPanel()

    plain = str(panel._render_body(st))

    assert "claude /login" in plain
