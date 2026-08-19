"""Contract tests pinning the metrics/comparison/report JSON schemas and the AgentAdapter protocol."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import jsonschema
import pytest

_CONTRACTS_DIR = (
    Path(__file__).resolve().parents[3] / "specs" / "019-agent-eval-harness" / "contracts"
)


def _load_schema(filename: str) -> dict:
    return json.loads((_CONTRACTS_DIR / filename).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def metrics_schema() -> dict:
    return _load_schema("metrics.schema.json")


@pytest.fixture(scope="module")
def comparison_schema() -> dict:
    return _load_schema("comparison.schema.json")


@pytest.fixture(scope="module")
def report_schema() -> dict:
    return _load_schema("report.schema.json")


@pytest.fixture
def adapter_base():
    """Deferred import: fails today because cabal.evals does not exist yet (the required Gate-3 state)."""
    from cabal.evals.adapters import base

    return base


# ---------------------------------------------------------------------------
# metrics.json fixtures
# ---------------------------------------------------------------------------


def _minimal_metrics() -> dict:
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "task_id": "sample-task",
        "config_name": "baseline",
        "repetition": 1,
        "adapter": "claude-code",
        "status": "completed",
        "failure_reason": None,
        "agent": {
            "tool_calls_total": None,
            "tool_calls_by_name": None,
            "num_turns": None,
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_tokens": None,
            "cost_usd": None,
            "wall_seconds": 12.5,
        },
        "diff": {
            "files_changed": 0,
            "insertions": 0,
            "deletions": 0,
            "unrequested_changes_count": None,
            "unrequested_files": None,
            "empty_diff": True,
        },
        "checks": [],
    }


def _rich_metrics() -> dict:
    metrics = _minimal_metrics()
    metrics["started_at"] = "2026-08-19T10:00:00Z"
    metrics["finished_at"] = "2026-08-19T10:05:00Z"
    metrics["agent"] = {
        "tool_calls_total": 12,
        "tool_calls_by_name": {"Edit": 5, "Read": 7},
        "num_turns": 4,
        "input_tokens": 20000,
        "output_tokens": 3000,
        "cache_read_tokens": 15000,
        "cost_usd": 0.42,
        "wall_seconds": 180.3,
    }
    metrics["diff"] = {
        "files_changed": 3,
        "insertions": 40,
        "deletions": 5,
        "unrequested_changes_count": 1,
        "unrequested_files": ["src/Extra.cs"],
        "empty_diff": False,
    }
    metrics["checks"] = [
        {
            "kind": "test",
            "cmd": ["dotnet", "test"],
            "status": "passed",
            "exit_code": 0,
            "passed_count": 10,
            "failed_count": 0,
            "duration_seconds": 30.1,
        },
        {
            "kind": "build",
            "cmd": ["dotnet", "build"],
            "status": "passed",
            "exit_code": 0,
            "duration_seconds": 5.4,
        },
    ]
    return metrics


class TestMetricsSchema:
    def test_minimal_metrics_fixture_validates_against_schema(self, metrics_schema: dict) -> None:
        """A run with no checks and no adapter-reported metrics is still a schema-valid artifact."""
        jsonschema.validate(_minimal_metrics(), metrics_schema)

    def test_rich_metrics_fixture_validates_against_schema(self, metrics_schema: dict) -> None:
        """A fully populated run (checks, tokens, cost) must also pass — schema isn't over-strict."""
        jsonschema.validate(_rich_metrics(), metrics_schema)

    def test_metrics_missing_schema_version_fails_validation(self, metrics_schema: dict) -> None:
        """schema_version anchors any future breaking-change migration; it can never be absent."""
        metrics = _minimal_metrics()
        del metrics["schema_version"]

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(metrics, metrics_schema)

    def test_metrics_agent_token_field_as_null_validates(self, metrics_schema: dict) -> None:
        """null is the required encoding for an adapter that cannot report a token count."""
        metrics = _minimal_metrics()
        assert metrics["agent"]["input_tokens"] is None

        jsonschema.validate(metrics, metrics_schema)

    def test_metrics_agent_token_field_as_string_fails_validation(self, metrics_schema: dict) -> None:
        """A stringified number is not the same as the numeric-or-null contract — must be rejected."""
        metrics = _minimal_metrics()
        metrics["agent"]["input_tokens"] = "1000"

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(metrics, metrics_schema)

    def test_metrics_with_unknown_top_level_property_fails_validation(
        self, metrics_schema: dict
    ) -> None:
        """additionalProperties: false must catch stray fields future code accidentally writes."""
        metrics = _minimal_metrics()
        metrics["extra_field"] = "nope"

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(metrics, metrics_schema)


# ---------------------------------------------------------------------------
# comparison.json fixtures
# ---------------------------------------------------------------------------


def _minimal_comparison() -> dict:
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "task_id": "sample-task",
        "baseline_config": "baseline",
        "candidate_config": "candidate",
        "judge_model": "claude-haiku-4-5-20251001",
        "pairs": [
            {
                "repetition": 1,
                "winner": "candidate",
                "confidence": 0.8,
                "order_agreement": True,
                "criteria": [],
                "truncated": False,
            }
        ],
    }


def _rich_comparison() -> dict:
    comparison = _minimal_comparison()
    comparison["rubrics"] = ["architecture", "coding-quality"]
    comparison["pairs"] = [
        {
            "repetition": 1,
            "winner": "candidate",
            "confidence": 0.8,
            "order_agreement": True,
            "criteria": [
                {"name": "clarity", "favored": "candidate", "note": "cleaner separation of concerns"},
            ],
            "truncated": True,
        },
        {
            "repetition": 2,
            "winner": "judge_error",
            "confidence": None,
            "order_agreement": True,
            "criteria": [],
            "truncated": False,
            "error_detail": "judge response was not valid JSON",
        },
    ]
    return comparison


class TestComparisonSchema:
    def test_minimal_comparison_fixture_validates_against_schema(
        self, comparison_schema: dict
    ) -> None:
        """A single-pair judged comparison is the smallest valid artifact."""
        jsonschema.validate(_minimal_comparison(), comparison_schema)

    def test_rich_comparison_fixture_validates_against_schema(self, comparison_schema: dict) -> None:
        """Multi-pair comparisons with rubrics, criteria, truncation, and judge_error must also pass."""
        jsonschema.validate(_rich_comparison(), comparison_schema)

    def test_comparison_missing_schema_version_fails_validation(
        self, comparison_schema: dict
    ) -> None:
        """Same versioning contract as metrics.json — never optional."""
        comparison = _minimal_comparison()
        del comparison["schema_version"]

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(comparison, comparison_schema)

    def test_comparison_order_agreement_false_with_winner_candidate_fails_validation(
        self, comparison_schema: dict
    ) -> None:
        """Position-bias control: disagreement across orders must force winner to tie/judge_error, never a side."""
        comparison = _minimal_comparison()
        comparison["pairs"][0]["order_agreement"] = False
        comparison["pairs"][0]["winner"] = "candidate"

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(comparison, comparison_schema)

    def test_comparison_order_agreement_false_with_winner_tie_validates(
        self, comparison_schema: dict
    ) -> None:
        """The allOf invariant's permitted side: disagreement paired with tie is exactly what it exists for."""
        comparison = _minimal_comparison()
        comparison["pairs"][0]["order_agreement"] = False
        comparison["pairs"][0]["winner"] = "tie"
        comparison["pairs"][0]["confidence"] = None

        jsonschema.validate(comparison, comparison_schema)

    def test_comparison_with_unknown_property_fails_validation(self, comparison_schema: dict) -> None:
        """additionalProperties: false applies here too, not just to metrics.json."""
        comparison = _minimal_comparison()
        comparison["extra_field"] = "nope"

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(comparison, comparison_schema)


# ---------------------------------------------------------------------------
# report.json fixtures
# ---------------------------------------------------------------------------

_SEVEN_DETERMINISTIC_METRICS = [
    "task_pass_rate",
    "test_pass_rate",
    "build_success_rate",
    "unrequested_changes",
    "tool_calls",
    "tokens_total",
    "wall_seconds",
]


def _report_metric_row(metric: str) -> dict:
    return {
        "metric": metric,
        "per_config": {
            "baseline": {"mean": 0.8, "min": 0.5, "max": 1.0, "stddev": 0.1, "n": 3},
            "candidate": {"mean": 0.9, "min": 0.6, "max": 1.0, "stddev": 0.05, "n": 3},
        },
    }


def _minimal_report() -> dict:
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "created_at": "2026-08-19T10:00:00Z",
        "tasks": ["sample-task"],
        "configs": ["baseline", "candidate"],
        "runs_per_cell": 3,
        "metrics_rows": [_report_metric_row(m) for m in _SEVEN_DETERMINISTIC_METRICS],
        "failures": [],
    }


def _rich_report() -> dict:
    report = _minimal_report()
    report["metrics_rows"].append(_report_metric_row("pairwise_win_rate"))
    report["failures"] = [
        {"task_id": "sample-task", "config_name": "candidate", "repetition": 2, "reason": "agent_timeout"},
    ]
    return report


class TestReportSchema:
    def test_minimal_report_fixture_validates_against_schema(self, report_schema: dict) -> None:
        """The seven deterministic metric rows are the floor SC-004 requires, with no judge data."""
        jsonschema.validate(_minimal_report(), report_schema)

    def test_rich_report_fixture_validates_against_schema(self, report_schema: dict) -> None:
        """Adding the pairwise-win-rate row and a failure entry must not break the schema."""
        jsonschema.validate(_rich_report(), report_schema)

    def test_report_missing_schema_version_fails_validation(self, report_schema: dict) -> None:
        """Same versioning contract as the other two artifacts."""
        report = _minimal_report()
        del report["schema_version"]

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(report, report_schema)

    def test_report_with_one_config_fails_validation(self, report_schema: dict) -> None:
        """A report is inherently a baseline-vs-candidate comparison — one config is not a comparison."""
        report = _minimal_report()
        report["configs"] = ["baseline"]

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(report, report_schema)

    def test_report_with_three_configs_fails_validation(self, report_schema: dict) -> None:
        """The harness only ever runs exactly baseline + candidate per invocation, never three-way."""
        report = _minimal_report()
        report["configs"] = ["baseline", "candidate", "extra"]

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(report, report_schema)

    def test_report_with_six_metric_rows_fails_validation(self, report_schema: dict) -> None:
        """SC-004's floor of >=7 rows must be enforced by the schema, not left to convention."""
        report = _minimal_report()
        report["metrics_rows"] = report["metrics_rows"][:6]

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(report, report_schema)

    def test_report_with_unknown_property_fails_validation(self, report_schema: dict) -> None:
        """additionalProperties: false applies to the aggregate artifact as well."""
        report = _minimal_report()
        report["extra_field"] = "nope"

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(report, report_schema)


# ---------------------------------------------------------------------------
# AgentAdapter protocol (contracts/agent-adapter.md)
# ---------------------------------------------------------------------------


class TestAdapterProtocol:
    def test_fake_adapter_exposes_required_protocol_members(self, adapter_base) -> None:
        """A drop-in adapter (Codex/Gemini) only needs name + check()/capabilities()/run() — no base class."""

        class FakeAdapter:
            name = "fake"

            def check(self) -> bool:
                return True

            def capabilities(self):
                return adapter_base.AdapterCapabilities(tokens=False, tool_calls=False, cost=False)

            def run(self, spec):
                return adapter_base.AgentRunResult(
                    status="completed",
                    failure_reason=None,
                    final_text="done",
                    exit_code=0,
                    wall_seconds=1.0,
                )

        fake = FakeAdapter()

        assert fake.name == "fake"
        assert callable(fake.check)
        assert callable(fake.capabilities)
        assert callable(fake.run)
        assert fake.check() is True

    def test_agent_run_spec_is_frozen_dataclass_with_contract_fields(
        self, adapter_base, tmp_path: Path
    ) -> None:
        """The matrix engine constructs AgentRunSpec by field name; every documented field must exist and stick."""
        spec = adapter_base.AgentRunSpec(
            prompt="do the thing",
            worktree=tmp_path,
            config_dir=None,
            settings_file=None,
            env={},
            model=None,
            timeout_seconds=900,
            skip_permissions=False,
            transcript_path=tmp_path / "transcript.jsonl",
        )

        assert spec.prompt == "do the thing"
        assert spec.worktree == tmp_path
        assert spec.timeout_seconds == 900

        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.prompt = "mutated"

    def test_agent_run_result_is_frozen_dataclass_with_contract_fields(self, adapter_base) -> None:
        """metrics.py reads AgentRunResult by field name; a mutable result risks a stale read mid-pipeline."""
        result = adapter_base.AgentRunResult(
            status="completed",
            failure_reason=None,
            final_text="all done",
            exit_code=0,
            wall_seconds=42.0,
        )

        assert result.status == "completed"
        assert result.exit_code == 0

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.status = "failed"

    def test_agent_run_result_failed_status_carries_failure_reason(self, adapter_base) -> None:
        """A failed run must always be explainable — matrix.py's failure inventory depends on this."""
        result = adapter_base.AgentRunResult(
            status="failed",
            failure_reason="agent_timeout",
            final_text="",
            exit_code=None,
            wall_seconds=900.0,
        )

        assert result.status == "failed"
        assert result.failure_reason == "agent_timeout"

    def test_adapter_capabilities_flags_are_booleans(self, adapter_base) -> None:
        """metrics.py branches on these flags to decide null-vs-real fields — they must be real booleans."""
        caps = adapter_base.AdapterCapabilities(tokens=True, tool_calls=True, cost=False)

        assert caps.tokens is True
        assert caps.tool_calls is True
        assert caps.cost is False

    def test_adapter_unavailable_error_is_raisable(self, adapter_base) -> None:
        """check()'s CLI-absent path signals via this exception type, distinct from a run-level failure."""
        with pytest.raises(adapter_base.AdapterUnavailableError):
            raise adapter_base.AdapterUnavailableError("claude CLI not found on PATH")
