# -*- coding: utf-8 -*-
"""Tests for session_reader — scanning, parsing, aggregation, delete, write_audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cabal.models.session import Session, TokenUsage
from cabal.session_pricing import load_pricing
from cabal.session_reader import (
    compute_summary,
    delete_session,
    infer_trigger,
    read_session,
    read_write_audit,
    scan_projects_dir,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _session(tmp_path: Path, content: str, project: str = "my-project") -> Session:
    project_dir = tmp_path / project
    project_dir.mkdir(parents=True, exist_ok=True)
    jsonl = project_dir / "abc123.jsonl"
    jsonl.write_text(content, encoding="utf-8")
    return Session(
        session_id="abc123",
        project_path=project,
        log_path=jsonl,
        file_size_bytes=jsonl.stat().st_size,
    )


def _ts(s: str) -> str:
    return f'"timestamp":"{s}"'


# ── scan_projects_dir ─────────────────────────────────────────────────────────

class TestScanProjectsDir:
    def test_returns_empty_list_for_nonexistent_root(self, tmp_path: Path):
        result = scan_projects_dir(tmp_path / "no-such-dir")

        assert result == []

    def test_returns_empty_list_for_empty_root(self, tmp_path: Path):
        (tmp_path / "projects").mkdir()

        result = scan_projects_dir(tmp_path / "projects")

        assert result == []

    def test_discovers_jsonl_files(self, tmp_path: Path):
        root = tmp_path / "projects"
        proj = root / "C%3A%2Fwork%2Ffoo"
        proj.mkdir(parents=True)
        (proj / "sess1.jsonl").write_text("{}", encoding="utf-8")
        (proj / "sess2.jsonl").write_text("{}", encoding="utf-8")
        (proj / "other.txt").write_text("ignore me", encoding="utf-8")

        result = scan_projects_dir(root)

        assert len(result) == 2
        assert all(s.session_id in ("sess1", "sess2") for s in result)

    def test_url_decodes_project_path(self, tmp_path: Path):
        root = tmp_path / "projects"
        proj = root / "C%3A%2Fwork%2Ffoo"
        proj.mkdir(parents=True)
        (proj / "sess.jsonl").write_text("{}", encoding="utf-8")

        result = scan_projects_dir(root)

        assert result[0].project_path == "C:/work/foo"


# ── read_session ─────────────────────────────────────────────────────────────

class TestReadSession:
    def test_parses_valid_entries(self, tmp_path: Path):
        content = (
            '{"type":"user","role":"user","content":"hello"}\n'
            '{"type":"assistant","role":"assistant","content":"hi","model":"claude-sonnet-4-6",'
            '"usage":{"input_tokens":10,"output_tokens":5,"cache_read_input_tokens":0,'
            '"cache_creation_input_tokens":0}}\n'
        )
        sess = _session(tmp_path, content)

        entries = read_session(sess)

        assert len(entries) == 2
        assert entries[0].type == "user"
        assert entries[1].type == "assistant"
        assert entries[1].usage is not None
        assert entries[1].usage.input_tokens == 10
        assert entries[1].usage.output_tokens == 5

    def test_skips_malformed_lines(self, tmp_path: Path):
        content = (
            '{"type":"user","content":"ok"}\n'
            'NOT VALID JSON\n'
            '{"type":"assistant","content":"ok2"}\n'
        )
        sess = _session(tmp_path, content)

        entries = read_session(sess)

        assert len(entries) == 2

    def test_returns_empty_for_missing_file(self, tmp_path: Path):
        sess = Session(
            session_id="missing",
            project_path="proj",
            log_path=tmp_path / "missing.jsonl",
        )

        entries = read_session(sess)

        assert entries == []

    def test_parses_tool_use_entry(self, tmp_path: Path):
        content = (
            '{"type":"tool_use","name":"Task","input":{"subagent_type":"python-architect",'
            '"description":"do something","prompt":"long prompt..."}}\n'
        )
        sess = _session(tmp_path, content)

        entries = read_session(sess)

        assert len(entries) == 1
        assert entries[0].tool_name == "Task"
        assert entries[0].tool_input["subagent_type"] == "python-architect"


# ── compute_summary ──────────────────────────────────────────────────────────

class TestComputeSummary:
    def _fixture_session(self, tmp_path: Path) -> Session:
        content = (
            '{"type":"user","content":"/speckit-plan build dashboard","timestamp":"2026-06-30T10:00:00.000Z"}\n'
            '{"type":"assistant","model":"claude-sonnet-4-6","usage":{"input_tokens":1200,'
            '"output_tokens":85,"cache_read_input_tokens":800,"cache_creation_input_tokens":0},'
            '"timestamp":"2026-06-30T10:00:03.000Z"}\n'
            '{"type":"tool_use","name":"Task","input":{"subagent_type":"python-architect",'
            '"description":"implement service","prompt":"..."},'
            '"timestamp":"2026-06-30T10:00:05.000Z"}\n'
        )
        return _session(tmp_path, content)

    def test_sums_input_tokens(self, tmp_path: Path):
        sess = self._fixture_session(tmp_path)
        entries = read_session(sess)

        summary = compute_summary(sess, entries, load_pricing())

        assert summary.total_input_tokens == 1200

    def test_sums_output_tokens(self, tmp_path: Path):
        sess = self._fixture_session(tmp_path)
        entries = read_session(sess)

        summary = compute_summary(sess, entries, load_pricing())

        assert summary.total_output_tokens == 85

    def test_computes_nonzero_cost(self, tmp_path: Path):
        sess = self._fixture_session(tmp_path)
        entries = read_session(sess)

        summary = compute_summary(sess, entries, load_pricing())

        assert summary.estimated_cost_usd > 0.0

    def test_detects_skill_invocation(self, tmp_path: Path):
        sess = self._fixture_session(tmp_path)
        entries = read_session(sess)

        summary = compute_summary(sess, entries, load_pricing())

        assert len(summary.skills) == 1
        assert summary.skills[0].skill_name == "speckit-plan"
        assert "build dashboard" in summary.skills[0].args

    def test_detects_agent_invocation(self, tmp_path: Path):
        sess = self._fixture_session(tmp_path)
        entries = read_session(sess)

        summary = compute_summary(sess, entries, load_pricing())

        assert len(summary.agents) == 1
        assert summary.agents[0].agent_type == "python-architect"

    def test_agent_trigger_is_skill(self, tmp_path: Path):
        sess = self._fixture_session(tmp_path)
        entries = read_session(sess)

        summary = compute_summary(sess, entries, load_pricing())

        assert summary.agents[0].triggered_by == "speckit-plan"

    def test_model_breakdown_populated(self, tmp_path: Path):
        sess = self._fixture_session(tmp_path)
        entries = read_session(sess)

        summary = compute_summary(sess, entries, load_pricing())

        assert "claude-sonnet-4-6" in summary.model_breakdown
        assert summary.model_breakdown["claude-sonnet-4-6"].input_tokens == 1200

    def test_empty_session_returns_zero_cost(self, tmp_path: Path):
        sess = _session(tmp_path, "")
        entries = read_session(sess)

        summary = compute_summary(sess, entries, load_pricing())

        assert summary.estimated_cost_usd == 0.0
        assert summary.total_input_tokens == 0


# ── delete_session ───────────────────────────────────────────────────────────

class TestDeleteSession:
    def test_removes_jsonl_file(self, tmp_path: Path):
        sess = _session(tmp_path, '{"type":"user"}')

        delete_session(sess)

        assert not sess.log_path.exists()

    def test_does_not_raise_if_already_gone(self, tmp_path: Path):
        sess = Session(
            session_id="gone",
            project_path="proj",
            log_path=tmp_path / "gone.jsonl",
        )

        delete_session(sess)  # should not raise


# ── infer_trigger ─────────────────────────────────────────────────────────────

class TestInferTrigger:
    def _entry(self, type_: str, content: str | None = None):
        from cabal.models.session import LogEntry
        return LogEntry(type=type_, content=content)

    def test_finds_nearest_skill(self):
        entries = [
            self._entry("user", "/speckit-plan build"),
            self._entry("assistant"),
            self._entry("tool_use"),
        ]

        result = infer_trigger(2, entries)

        assert result == "speckit-plan"

    def test_returns_direct_when_no_prior_user(self):
        entries = [self._entry("tool_use")]

        result = infer_trigger(0, entries)

        assert result == "direct"

    def test_skips_non_user_entries(self):
        entries = [
            self._entry("user", "/code-review"),
            self._entry("assistant"),
            self._entry("tool_result"),
            self._entry("tool_use"),
        ]

        result = infer_trigger(3, entries)

        assert result == "code-review"


# ── read_write_audit ──────────────────────────────────────────────────────────

class TestReadWriteAudit:
    def test_parses_valid_entries(self, tmp_path: Path):
        audit = tmp_path / "write_audit.jsonl"
        audit.write_text(
            '{"ts":"2026-06-30T10:00:00+00:00","tool":"Write","path":"C:/foo/bar.py"}\n'
            '{"ts":"2026-06-30T10:01:00+00:00","tool":"Edit","path":"C:/foo/baz.py"}\n',
            encoding="utf-8",
        )

        events = read_write_audit(audit)

        assert len(events) == 2
        assert events[0].tool == "Write"
        assert events[1].tool == "Edit"

    def test_returns_empty_when_file_missing(self, tmp_path: Path):
        events = read_write_audit(tmp_path / "missing.jsonl")

        assert events == []

    def test_since_filter_excludes_old_entries(self, tmp_path: Path):
        audit = tmp_path / "write_audit.jsonl"
        audit.write_text(
            '{"ts":"2026-06-30T09:00:00+00:00","tool":"Write","path":"old.py"}\n'
            '{"ts":"2026-06-30T11:00:00+00:00","tool":"Edit","path":"new.py"}\n',
            encoding="utf-8",
        )
        cutoff = datetime(2026, 6, 30, 10, 0, 0, tzinfo=timezone.utc)

        events = read_write_audit(audit, since=cutoff)

        assert len(events) == 1
        assert events[0].path == "new.py"
