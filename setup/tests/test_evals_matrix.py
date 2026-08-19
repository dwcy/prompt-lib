# -*- coding: utf-8 -*-
"""Unit tests for cabal.evals.matrix: cell enumeration, resume, failure isolation, atomicity."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from cabal.evals.adapters.base import (
    AdapterCapabilities,
    AdapterStatus,
    AdapterUnavailableError,
    AgentRunResult,
    AgentRunSpec,
)
from cabal.evals.definitions_model import CheckSpec, ConfigProfile, EvalConfig, Task
from cabal.evals.matrix import (
    FAILURE_ADAPTER_UNAVAILABLE,
    MANIFEST_FILENAME,
    METRICS_FILENAME,
    run_matrix,
)

# Shared helpers --------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    )
    return result.stdout


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    """A real git repo with one commit, used as the worktree source for every cell."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "evals-test@example.com")
    _git(repo, "config", "user.name", "Evals Test")
    _write(repo / "tracked.txt", "original\n")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "initial commit")
    return repo


def _make_profile(name: str, *, env: dict[str, str] | None = None) -> ConfigProfile:
    return ConfigProfile(
        name=name,
        description=f"{name} profile",
        user_overlay=None,
        project_overlay=None,
        settings_file=None,
        env=dict(env or {}),
    )


def _make_task(task_id: str, repo: Path, ref: str) -> Task:
    return Task(
        id=task_id,
        title=f"Task {task_id}",
        repo=repo,
        ref=ref,
        prompt=f"prompt for {task_id}",
        checks=[
            CheckSpec(kind="custom", cmd=["python", "-c", "pass"], parser="exit-code", timeout_seconds=30)
        ],
        expected_files=[],
        rubrics=[],
        timeout_seconds=None,
        skip_permissions=False,
    )


def _eval_config(results_dir: Path) -> EvalConfig:
    return EvalConfig(
        runs_per_cell=1,
        adapter="fake-adapter",
        agent_model=None,
        run_timeout_seconds=60,
        check_timeout_seconds=30,
        results_dir=results_dir,
        judge_model=None,
        judge_diff_char_limit=20000,
    )


@dataclass(frozen=True)
class _MatrixInputs:
    """Everything one `run_matrix` invocation needs, minus the adapter (each test picks its own)."""

    tasks: list[Task]
    baseline: ConfigProfile
    candidate: ConfigProfile
    eval_config: EvalConfig
    results_dir: Path


@pytest.fixture
def matrix_inputs(scratch_repo: Path, tmp_path: Path) -> _MatrixInputs:
    """Two tasks x two distinct-env configs, pinned at the repo's single commit."""
    commit = _git(scratch_repo, "rev-parse", "HEAD").strip()
    tasks = [_make_task("task-a", scratch_repo, commit), _make_task("task-b", scratch_repo, commit)]
    baseline = _make_profile("baseline", env={"BASELINE": "1"})
    candidate = _make_profile("candidate", env={"CANDIDATE": "1"})
    results_dir = tmp_path / "results"
    return _MatrixInputs(tasks, baseline, candidate, _eval_config(results_dir), results_dir)


@pytest.fixture
def identical_profile_inputs(scratch_repo: Path, tmp_path: Path) -> _MatrixInputs:
    """One task, two byte-identical profiles -- backs the no-op comparison warning."""
    commit = _git(scratch_repo, "rev-parse", "HEAD").strip()
    tasks = [_make_task("task-a", scratch_repo, commit)]
    baseline = _make_profile("baseline")
    candidate = _make_profile("candidate")
    results_dir = tmp_path / "results"
    return _MatrixInputs(tasks, baseline, candidate, _eval_config(results_dir), results_dir)


def _write_fake_transcript(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": "Edit"}]}}),
        json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "done", "num_turns": 1}),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass
class FakeAdapter:
    """Records every spec it was asked to run; fails only for prompts in `fail_prompts`."""

    name: str = "fake-adapter"
    fail_prompts: frozenset[str] = field(default_factory=frozenset)
    calls: list[str] = field(default_factory=list)

    def check(self) -> AdapterStatus:
        return AdapterStatus(adapter=self.name, available=True)

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(tokens=False, tool_calls=True, cost=False)

    def run(self, spec: AgentRunSpec) -> AgentRunResult:
        self.calls.append(spec.prompt)
        if spec.prompt in self.fail_prompts:
            raise AdapterUnavailableError(f"simulated CLI unavailable for {spec.prompt!r}")
        _write_fake_transcript(spec.transcript_path)
        (spec.worktree / "agent-output.txt").write_text(f"processed {spec.prompt}\n", encoding="utf-8")
        return AgentRunResult(
            status="completed", failure_reason=None, final_text="done", exit_code=0, wall_seconds=0.01
        )


def _run(inputs: _MatrixInputs, adapter: FakeAdapter, *, runs: int = 1, resume_run_id: str | None = None):
    return run_matrix(
        inputs.eval_config,
        inputs.tasks,
        inputs.baseline,
        inputs.candidate,
        runs,
        inputs.results_dir,
        adapter,
        resume_run_id=resume_run_id,
    )


# Enumeration -----------------------------------------------------------------


class TestEnumeration:
    def test_run_matrix_enumerates_exactly_the_expected_cell_tree(self, matrix_inputs: _MatrixInputs) -> None:
        """Two tasks x two configs x two repetitions must produce exactly eight recorded cells."""
        # Arrange
        adapter = FakeAdapter()

        # Act
        summary = _run(matrix_inputs, adapter, runs=2)

        # Assert
        expected_cells = {
            (task.id, prof.name, rep)
            for task in matrix_inputs.tasks
            for prof in (matrix_inputs.baseline, matrix_inputs.candidate)
            for rep in (1, 2)
        }
        actual_cells = {(cell.task_id, cell.config_name, cell.repetition) for cell in summary.cells}
        assert actual_cells == expected_cells

    def test_run_matrix_writes_run_json_manifest_reflecting_the_selection(
        self, matrix_inputs: _MatrixInputs
    ) -> None:
        """The manifest must persist enough of the invocation for `run --resume` to restore it."""
        # Arrange
        adapter = FakeAdapter()

        # Act
        summary = _run(matrix_inputs, adapter, runs=2)

        # Assert
        manifest = json.loads((summary.run_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        assert manifest["baseline"] == "baseline"
        assert manifest["candidate"] == "candidate"
        assert manifest["runs"] == 2
        assert sorted(manifest["tasks"]) == ["task-a", "task-b"]
        assert manifest["adapter"] == "fake-adapter"


# Resume ------------------------------------------------------------------------


class TestResume:
    def test_resume_with_same_run_id_never_recalls_the_adapter(self, matrix_inputs: _MatrixInputs) -> None:
        """Re-invoking a completed run-id must skip every cell without re-running the agent."""
        # Arrange
        adapter = FakeAdapter()
        first = _run(matrix_inputs, adapter, runs=1)
        calls_after_first = len(adapter.calls)

        # Act
        _run(matrix_inputs, adapter, runs=1, resume_run_id=first.run_id)

        # Assert
        assert len(adapter.calls) == calls_after_first

    def test_resume_with_same_run_id_reports_all_cells_skipped(self, matrix_inputs: _MatrixInputs) -> None:
        """A fully-completed run resumed again must classify every cell as skipped, not re-completed."""
        # Arrange
        adapter = FakeAdapter()
        first = _run(matrix_inputs, adapter, runs=1)

        # Act
        second = _run(matrix_inputs, adapter, runs=1, resume_run_id=first.run_id)

        # Assert
        assert second.skipped == len(second.cells)


# Failure isolation ---------------------------------------------------------------


class TestFailureIsolation:
    def test_one_failing_cell_does_not_prevent_the_others_from_completing(
        self, matrix_inputs: _MatrixInputs
    ) -> None:
        """A single adapter failure must be isolated to its own cells, never abort the matrix."""
        # Arrange
        failing_task = matrix_inputs.tasks[0]
        adapter = FakeAdapter(fail_prompts=frozenset({failing_task.prompt}))

        # Act
        summary = _run(matrix_inputs, adapter, runs=1)

        # Assert
        assert summary.completed == 2
        assert summary.failed == 2

    def test_failing_cell_metrics_json_records_the_machine_readable_reason(
        self, matrix_inputs: _MatrixInputs
    ) -> None:
        """Downstream reporting depends on failure_reason being one of the schema's pinned values."""
        # Arrange
        failing_task = matrix_inputs.tasks[0]
        adapter = FakeAdapter(fail_prompts=frozenset({failing_task.prompt}))

        # Act
        summary = _run(matrix_inputs, adapter, runs=1)

        # Assert
        cell_metrics_path = (
            summary.run_dir / failing_task.id / matrix_inputs.baseline.name / "1" / METRICS_FILENAME
        )
        cell_metrics = json.loads(cell_metrics_path.read_text(encoding="utf-8"))
        assert cell_metrics["status"] == "failed"
        assert cell_metrics["failure_reason"] == FAILURE_ADAPTER_UNAVAILABLE


# No-op profiles ------------------------------------------------------------------


class TestNoOpProfiles:
    def test_byte_identical_profiles_emit_a_no_op_warning(
        self, identical_profile_inputs: _MatrixInputs
    ) -> None:
        """Comparing a profile against itself is meaningless -- the harness must say so."""
        # Arrange
        adapter = FakeAdapter()

        # Act & Assert
        with pytest.warns(UserWarning, match="no-op comparison"):
            _run(identical_profile_inputs, adapter, runs=1)

    def test_byte_identical_profiles_still_execute_every_cell(
        self, identical_profile_inputs: _MatrixInputs
    ) -> None:
        """The no-op warning is informational only -- it must never skip the run itself."""
        # Arrange
        adapter = FakeAdapter()

        # Act
        with pytest.warns(UserWarning):
            summary = _run(identical_profile_inputs, adapter, runs=1)

        # Assert
        assert summary.completed == 2


# Atomicity -----------------------------------------------------------------------


class TestAtomicity:
    def test_run_matrix_leaves_no_tmp_files_in_the_results_tree(self, matrix_inputs: _MatrixInputs) -> None:
        """The `.tmp` + rename dance is an implementation detail -- none may survive a completed run."""
        # Arrange
        adapter = FakeAdapter()

        # Act
        summary = _run(matrix_inputs, adapter, runs=1)

        # Assert
        assert list(summary.run_dir.rglob("*.tmp")) == []

    def test_resume_reruns_a_cell_whose_metrics_json_was_removed(self, matrix_inputs: _MatrixInputs) -> None:
        """A cell directory without a parseable metrics.json is incomplete, no matter its history."""
        # Arrange
        adapter = FakeAdapter()
        first = _run(matrix_inputs, adapter, runs=1)
        target_task = matrix_inputs.tasks[0]
        cell_dir = first.run_dir / target_task.id / matrix_inputs.baseline.name / "1"
        (cell_dir / METRICS_FILENAME).unlink()
        calls_before_resume = len(adapter.calls)

        # Act
        second = _run(matrix_inputs, adapter, runs=1, resume_run_id=first.run_id)

        # Assert
        assert len(adapter.calls) == calls_before_resume + 1
        rerun_cell = next(
            cell
            for cell in second.cells
            if cell.task_id == target_task.id and cell.config_name == matrix_inputs.baseline.name
        )
        assert rerun_cell.status == "completed"


# Worktree hygiene ------------------------------------------------------------------


class TestWorktreeHygiene:
    def test_worktree_list_shows_only_the_main_tree_after_the_matrix(
        self, matrix_inputs: _MatrixInputs, scratch_repo: Path
    ) -> None:
        """Every per-cell worktree must be removed by the time the matrix returns -- none may leak."""
        # Arrange
        adapter = FakeAdapter()

        # Act
        _run(matrix_inputs, adapter, runs=2)

        # Assert
        listing = _git(scratch_repo, "worktree", "list", "--porcelain")
        assert listing.count("worktree ") == 1
