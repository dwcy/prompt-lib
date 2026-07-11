# -*- coding: utf-8 -*-
"""Unit tests for context_guard_policy: load/save/source over a temp policy file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal import context_guard_policy


@pytest.fixture
def tmp_policy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / ".claude" / "context-guard-policy.json"
    monkeypatch.setattr(context_guard_policy, "POLICY_PATH", path)
    return path


def test_load_policy_without_a_file_returns_builtin_defaults(tmp_policy_path):
    policy = context_guard_policy.load_policy()

    assert policy == context_guard_policy.BUILTIN_DEFAULTS
    assert policy["enabled"] is False


def test_load_policy_merges_user_file_over_defaults(tmp_policy_path):
    tmp_policy_path.parent.mkdir(parents=True)
    tmp_policy_path.write_text(json.dumps({"enabled": True}), encoding="utf-8")

    policy = context_guard_policy.load_policy()

    assert policy["enabled"] is True
    assert policy["threshold_percent"] == context_guard_policy.BUILTIN_DEFAULTS[
        "threshold_percent"
    ]


def test_load_policy_ignores_corrupt_file_and_falls_back_to_defaults(tmp_policy_path):
    tmp_policy_path.parent.mkdir(parents=True)
    tmp_policy_path.write_text("{not json", encoding="utf-8")

    policy = context_guard_policy.load_policy()

    assert policy == context_guard_policy.BUILTIN_DEFAULTS


def test_save_policy_writes_file_and_creates_parent_dir(tmp_policy_path):
    written = context_guard_policy.save_policy(
        {"enabled": True, "threshold_percent": 90, "max_context_tokens": 1000000}
    )

    assert written == tmp_policy_path
    assert json.loads(tmp_policy_path.read_text(encoding="utf-8")) == {
        "enabled": True,
        "threshold_percent": 90,
        "max_context_tokens": 1000000,
    }


def test_saved_policy_round_trips_through_load(tmp_policy_path):
    context_guard_policy.save_policy(
        {"enabled": True, "threshold_percent": 65, "max_context_tokens": 400000}
    )

    policy = context_guard_policy.load_policy()

    assert policy["enabled"] is True
    assert policy["threshold_percent"] == 65
    assert policy["max_context_tokens"] == 400000


def test_policy_source_reports_builtin_defaults_when_no_file(tmp_policy_path):
    source = context_guard_policy.policy_source()

    assert source == "<built-in defaults — feature disabled>"


def test_policy_source_reports_the_file_path_once_saved(tmp_policy_path):
    context_guard_policy.save_policy({"enabled": False})

    assert context_guard_policy.policy_source() == tmp_policy_path
