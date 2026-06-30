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
    infer_session_tree,
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

    def test_parses_real_nested_format(self, tmp_path: Path):
        """Real Claude Code transcripts nest data under a 'message' key."""
        content = (
            '{"type":"user","message":{"role":"user","content":"/speckit-plan build it"},'
            '"timestamp":"2026-06-30T10:00:00.000Z","requestId":null}\n'
            '{"type":"assistant","message":{"model":"claude-sonnet-4-6",'
            '"content":[{"type":"text","text":"sure"}],'
            '"usage":{"input_tokens":50,"output_tokens":20,'
            '"cache_read_input_tokens":100,"cache_creation_input_tokens":0}},'
            '"timestamp":"2026-06-30T10:00:03.000Z","requestId":"req_abc"}\n'
            '{"type":"assistant","message":{"model":"claude-sonnet-4-6",'
            '"content":[{"type":"tool_use","name":"Agent",'
            '"input":{"subagent_type":"python-architect","description":"do it","prompt":"..."}}],'
            '"usage":{"input_tokens":50,"output_tokens":20,'
            '"cache_read_input_tokens":100,"cache_creation_input_tokens":0}},'
            '"timestamp":"2026-06-30T10:00:04.000Z","requestId":"req_abc"}\n'
        )
        sess = _session(tmp_path, content)

        entries = read_session(sess)

        assert len(entries) == 3
        assert entries[0].content == "/speckit-plan build it"
        assert entries[1].usage is not None
        assert entries[1].usage.input_tokens == 50
        assert entries[1].model == "claude-sonnet-4-6"
        assert entries[2].tool_name == "Agent"
        assert entries[1].request_id == "req_abc"

    def test_deduplicates_usage_by_request_id(self, tmp_path: Path):
        """Entries sharing a requestId count tokens only once."""
        shared = (
            '"model":"claude-sonnet-4-6",'
            '"usage":{"input_tokens":100,"output_tokens":40,'
            '"cache_read_input_tokens":0,"cache_creation_input_tokens":0}'
        )
        content = (
            f'{{"type":"assistant","message":{{{shared},"content":[]}},'
            f'"requestId":"req_1","timestamp":"2026-06-30T10:00:01.000Z"}}\n'
            f'{{"type":"assistant","message":{{{shared},"content":[]}},'
            f'"requestId":"req_1","timestamp":"2026-06-30T10:00:02.000Z"}}\n'
        )
        sess = _session(tmp_path, content)
        entries = read_session(sess)

        summary = compute_summary(sess, entries, load_pricing())

        assert summary.total_input_tokens == 100
        assert summary.total_output_tokens == 40


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


# ── infer_session_tree ───────────────────────────────────────────────────────

class TestInferSessionTree:
    def _summary(
        self,
        session_id: str,
        project: str,
        start: datetime,
        duration: float,
    ) -> "SessionSummary":
        from cabal.models.session import SessionSummary
        return SessionSummary(
            session_id=session_id,
            project_path=project,
            start_time=start,
            duration_seconds=duration,
            total_input_tokens=0,
            total_output_tokens=0,
            total_cache_read_tokens=0,
            total_cache_write_tokens=0,
            estimated_cost_usd=0.0,
        )

    def _dt(self, hour: int, minute: int = 0) -> datetime:
        return datetime(2026, 6, 30, hour, minute, tzinfo=timezone.utc)

    def test_child_within_parent_time_range_is_linked(self):
        parent = self._summary("parent", "proj", self._dt(9), 3600.0)
        child = self._summary("child", "proj", self._dt(9, 30), 600.0)

        infer_session_tree([parent, child])

        assert child.parent_session_id == "parent"
        assert "child" in parent.child_session_ids

    def test_parent_gets_child_in_child_list(self):
        parent = self._summary("parent", "proj", self._dt(9), 3600.0)
        child = self._summary("child", "proj", self._dt(9, 10), 300.0)

        infer_session_tree([parent, child])

        assert "child" in parent.child_session_ids

    def test_non_overlapping_sessions_are_not_linked(self):
        first = self._summary("first", "proj", self._dt(9), 1800.0)
        second = self._summary("second", "proj", self._dt(12), 1800.0)

        infer_session_tree([first, second])

        assert first.parent_session_id is None
        assert second.parent_session_id is None
        assert first.child_session_ids == []
        assert second.child_session_ids == []

    def test_longer_session_is_not_child_of_shorter(self):
        short = self._summary("short", "proj", self._dt(9), 600.0)
        long = self._summary("long", "proj", self._dt(9, 5), 3600.0)

        infer_session_tree([short, long])

        assert long.parent_session_id is None
        assert short.parent_session_id is None

    def test_different_project_sessions_are_not_linked(self):
        session_a = self._summary("a", "project-alpha", self._dt(9), 3600.0)
        session_b = self._summary("b", "project-beta", self._dt(9, 10), 300.0)

        infer_session_tree([session_a, session_b])

        assert session_b.parent_session_id is None
        assert session_a.child_session_ids == []

    def test_tightest_parent_wins(self):
        outer = self._summary("outer", "proj", self._dt(8), 7200.0)
        inner = self._summary("inner", "proj", self._dt(9), 3600.0)
        child = self._summary("child", "proj", self._dt(9, 30), 600.0)

        infer_session_tree([outer, inner, child])

        assert child.parent_session_id == "inner"
        assert "child" in inner.child_session_ids
        assert "child" not in outer.child_session_ids

    def test_session_without_timestamps_is_skipped(self):
        from cabal.models.session import SessionSummary
        parent = self._summary("parent", "proj", self._dt(9), 3600.0)
        no_ts = SessionSummary(
            session_id="no-ts",
            project_path="proj",
            start_time=None,
            duration_seconds=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            total_cache_read_tokens=0,
            total_cache_write_tokens=0,
            estimated_cost_usd=0.0,
        )

        infer_session_tree([parent, no_ts])

        assert no_ts.parent_session_id is None
        assert parent.child_session_ids == []


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
