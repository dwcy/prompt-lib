# -*- coding: utf-8 -*-
"""Unit tests for cabal.evals.adapters: registry resolution, capability gating, claude-code probes."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

import cabal.evals.adapters as adapters_module
from cabal.evals import cli_run
from cabal.evals.adapters import UnknownAdapterError, get_adapter, registered_names
from cabal.evals.adapters.base import (
    AdapterCapabilities,
    AdapterStatus,
    AdapterUnavailableError,
    AgentRunResult,
    AgentRunSpec,
)
from cabal.evals.adapters.claude_code import ADAPTER_NAME, ClaudeCodeAdapter
from cabal.evals.definitions_model import CheckSpec, ConfigProfile, EvalConfig, Task
from cabal.evals.matrix import METRICS_FILENAME, run_matrix

# Registry --------------------------------------------------------------------


class TestAdapterRegistry:
    def test_get_adapter_resolves_the_claude_code_registration(self) -> None:
        """claude-code is registered at import time; resolving it must return a usable adapter."""
        # Act
        adapter = get_adapter("claude-code")

        # Assert
        assert adapter.name == "claude-code"

    def test_get_adapter_unknown_name_raises_with_the_name_in_the_message(self) -> None:
        """A typo'd adapter name must fail loudly and name itself, not silently fall back."""
        # Act & Assert
        with pytest.raises(UnknownAdapterError, match="totally-not-a-real-adapter"):
            get_adapter("totally-not-a-real-adapter")

    def test_cli_run_catches_the_same_unknown_adapter_error_type(self) -> None:
        """cli_run's `_resolve_adapter` must handle exactly this exception type, not a stand-in."""
        # Assert
        assert cli_run.UnknownAdapterError is UnknownAdapterError

    def test_registered_names_includes_claude_code(self) -> None:
        """The registry must expose claude-code among its known names for validate-time checks."""
        # Assert
        assert "claude-code" in registered_names()


class TestAdapterRegistryDocstringContract:
    def test_adapters_package_docstring_documents_registration_and_capabilities(self) -> None:
        """Cheap drift guard: the drop-in contract for future adapters must still be documented."""
        # Arrange
        docstring = (adapters_module.__doc__ or "").lower()

        # Assert
        assert "register(" in docstring
        assert "capabilit" in docstring


# Capability-gated nulls end-to-end --------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    )
    return result.stdout


@dataclass
class _NoCapabilitiesAdapter:
    """A FakeAdapter that declares no tokens/tool_calls/cost support but reports them anyway."""

    name: str = "no-capabilities-adapter"

    def check(self) -> AdapterStatus:
        return AdapterStatus(adapter=self.name, available=True)

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(tokens=False, tool_calls=False, cost=False)

    def run(self, spec: AgentRunSpec) -> AgentRunResult:
        lines = [
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "tool_use", "id": "1", "name": "Edit"}]},
                }
            ),
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": "done",
                    "num_turns": 1,
                    "total_cost_usd": 0.42,
                    "usage": {
                        "input_tokens": 12345,
                        "output_tokens": 6789,
                        "cache_read_input_tokens": 100,
                    },
                }
            ),
        ]
        spec.transcript_path.parent.mkdir(parents=True, exist_ok=True)
        spec.transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return AgentRunResult(
            status="completed", failure_reason=None, final_text="done", exit_code=0, wall_seconds=0.01
        )


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    """A real git repo with one commit, used as the worktree source for the matrix cell."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "evals-test@example.com")
    _git(repo, "config", "user.name", "Evals Test")
    (repo / "tracked.txt").write_text("original\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "initial commit")
    return repo


class TestCapabilityGatingEndToEnd:
    def test_capabilities_false_forces_null_metrics_even_when_the_transcript_reports_usage(
        self, scratch_repo: Path, tmp_path: Path
    ) -> None:
        """US6-AS2: capabilities() must gate metrics extraction -- transcript content alone must not
        leak token/tool-call/cost figures past an adapter that declares it cannot supply them."""
        # Arrange
        commit = _git(scratch_repo, "rev-parse", "HEAD").strip()
        task = Task(
            id="task-a",
            title="Task A",
            repo=scratch_repo,
            ref=commit,
            prompt="do the thing",
            checks=[CheckSpec(kind="custom", cmd=["python", "-c", "pass"], parser="exit-code", timeout_seconds=30)],
            expected_files=[],
            rubrics=[],
            timeout_seconds=None,
            skip_permissions=False,
        )
        profile = ConfigProfile(
            name="baseline", description="baseline profile", user_overlay=None,
            project_overlay=None, settings_file=None, env={},
        )
        eval_config = EvalConfig(
            runs_per_cell=1, adapter="no-capabilities-adapter", agent_model=None,
            run_timeout_seconds=60, check_timeout_seconds=30, results_dir=tmp_path / "results",
            judge_model=None, judge_diff_char_limit=20000,
        )
        adapter = _NoCapabilitiesAdapter()

        # Act
        with pytest.warns(UserWarning, match="no-op comparison"):
            summary = run_matrix(eval_config, [task], profile, profile, 1, eval_config.results_dir, adapter)

        # Assert
        metrics = json.loads(
            (summary.run_dir / "task-a" / "baseline" / "1" / METRICS_FILENAME).read_text(encoding="utf-8")
        )
        agent = metrics["agent"]
        assert (
            agent["tool_calls_total"],
            agent["input_tokens"],
            agent["output_tokens"],
            agent["cost_usd"],
        ) == (None, None, None, None)


# claude-code adapter -----------------------------------------------------------------


class TestClaudeCodeAdapterCapabilities:
    def test_capabilities_are_all_true(self) -> None:
        """The real CLI genuinely reports tokens, tool calls and cost -- declare all three True."""
        # Arrange
        adapter = ClaudeCodeAdapter()

        # Act
        capabilities = adapter.capabilities()

        # Assert
        assert capabilities == AdapterCapabilities(tokens=True, tool_calls=True, cost=True)


class TestClaudeCodeAdapterCheck:
    def test_check_returns_unavailable_status_without_raising_when_cli_is_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing `claude` executable must be reported via AdapterStatus, never an exception."""
        # Arrange
        monkeypatch.setattr("cabal.evals.adapters.claude_code.shutil.which", lambda name: None)
        adapter = ClaudeCodeAdapter()

        # Act
        status = adapter.check()

        # Assert
        assert status == AdapterStatus(
            adapter=ADAPTER_NAME, available=False, detail="`claude` not found on PATH"
        )


class TestClaudeCodeAdapterRun:
    def test_run_raises_adapter_unavailable_when_cli_is_absent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """`run()` must fail fast with AdapterUnavailableError, distinct from a run-level failure."""
        # Arrange
        monkeypatch.setattr("cabal.evals.adapters.claude_code.shutil.which", lambda name: None)
        adapter = ClaudeCodeAdapter()
        spec = AgentRunSpec(
            prompt="do the thing",
            worktree=tmp_path,
            config_dir=None,
            settings_file=None,
            env={},
            model=None,
            timeout_seconds=60,
            skip_permissions=False,
            transcript_path=tmp_path / "transcript.jsonl",
        )

        # Act & Assert
        with pytest.raises(AdapterUnavailableError):
            adapter.run(spec)

    def test_run_with_hung_process_times_out_and_kills_the_process_tree(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """FR-005 / adapter contract #2: at the deadline the process tree dies and the run
        records agent_timeout — a leaked child would poison every subsequent cell."""
        import sys

        # Arrange
        monkeypatch.setattr(
            "cabal.evals.adapters.claude_code.shutil.which", lambda name: sys.executable
        )
        monkeypatch.setattr(
            "cabal.evals.adapters.claude_code._build_command",
            lambda exe, spec: [exe, "-c", "import time; time.sleep(60)"],
        )
        adapter = ClaudeCodeAdapter()
        spec = AgentRunSpec(
            prompt="irrelevant",
            worktree=tmp_path,
            config_dir=None,
            settings_file=None,
            env={},
            model=None,
            timeout_seconds=2,
            skip_permissions=False,
            transcript_path=tmp_path / "transcript.jsonl",
        )

        # Act
        result = adapter.run(spec)

        # Assert
        assert (
            result.status == "failed"
            and result.failure_reason == "agent_timeout"
            and result.wall_seconds < 30
        )
