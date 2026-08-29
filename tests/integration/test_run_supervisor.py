"""Integration tests for the run-supervisor reconciliation state machine (T015).

Covers research.md R2's stranded-`running` bug (a job alive at a hard shutdown stays
`running` in the `jobs` table forever unless reconciled at read time), the outcome-mapping
table locked down in `_CODEGEN_OUTCOME_STATES`, the T010 guarantee that `interrupted` is
never written back to `jobs.state`, the T011 post-restart exclusive-resource liveness
check, the T009 evals reconciliation rule reusing `cabal.evals.matrix.is_cell_complete`,
and the T014 distinctness of the `no_benchmark_tree` / `definitions_invalid` availability
reasons. Real Storage (sqlite), real filesystem artifact trees, and real OS pids
throughout -- the whole design rests on reading real artifacts and real process liveness,
so none of that is mocked here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import get_args

import pytest

from cabal.evals import matrix
from cabal.webapi import jobs as jobs_module
from cabal.webapi.envelope import utc_now_iso
from cabal.webapi.run_supervisor import (
    SupervisedRun,
    check_resource_liveness,
    presented_state,
    probe_evals_availability,
    reconcile_state,
)
from cabal.webapi.storage import Storage, WriteGuard

# Fixtures -------------------------------------------------------------------


@pytest.fixture
def storage(tmp_path: Path) -> Iterator[Storage]:
    handle = Storage(tmp_path / "webapi.sqlite3")
    try:
        yield handle
    finally:
        handle.close()


@pytest.fixture
def dead_pid() -> int:
    """A pid guaranteed not to be alive: spawn a trivial process and reap it."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    pid = proc.pid
    proc.wait(timeout=5)
    return pid


@pytest.fixture
def alive_pid() -> int:
    """The current test process's own pid -- guaranteed alive for the test's duration."""
    return os.getpid()


def _make_run(
    *,
    kind: str,
    pid: int | None,
    artifact_root: Path | str,
    exclusive_resource: str = "codegen",
    job_id: str = "job-1",
    run_id: str = "run-1",
) -> SupervisedRun:
    return SupervisedRun(
        job_id=job_id,
        kind=kind,  # type: ignore[arg-type]
        run_id=run_id,
        pid=pid,
        artifact_root=str(artifact_root),
        exclusive_resource=exclusive_resource,  # type: ignore[arg-type]
    )


def _write_codegen_record(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_evals_manifest(
    run_dir: Path, *, tasks: list[str], runs: int, baseline: str = "baseline", candidate: str = "candidate"
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_dir.name,
        "tasks": tasks,
        "runs": runs,
        "baseline": baseline,
        "candidate": candidate,
    }
    (run_dir / matrix.MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")


def _write_cell_metrics(run_dir: Path, *, task_id: str, profile_name: str, repetition: int) -> None:
    cell_dir = run_dir / task_id / profile_name / str(repetition)
    cell_dir.mkdir(parents=True, exist_ok=True)
    (cell_dir / matrix.METRICS_FILENAME).write_text(json.dumps({"checks": []}), encoding="utf-8")


# The motivating case (research.md R2) ----------------------------------------
# A jobs row alive at a hard shutdown is never rehydrated by `JobManager.__init__`
# (memory-only, per R2) and only terminal states are persisted -- so without read-time
# reconciliation it would stay `running` forever. These tests use `codegen.run`, whose
# artifact is a single record file, so "incomplete" is naturally "the record was never
# written" -- the most direct rendering of a process that died before finishing.


class TestStrandedRunningReconciliation:
    def test_reconcile_state_dead_pid_and_missing_record_returns_interrupted(
        self, dead_pid: int, tmp_path: Path
    ) -> None:
        """The stranded-running case: backend died, pid is gone, the run never got far
        enough to write its record at all -- must present as interrupted, not crash."""
        # Arrange
        record_path = tmp_path / "runs" / "run-1.json"
        run = _make_run(kind="codegen.run", pid=dead_pid, artifact_root=record_path)

        # Act
        result = reconcile_state(run)

        # Assert
        assert result == "interrupted"

    def test_reconcile_state_dead_pid_and_record_missing_outcome_field_returns_interrupted(
        self, dead_pid: int, tmp_path: Path
    ) -> None:
        """A record written mid-run (process died before the outcome was decided) is
        also incomplete -- distinct from the missing-file case above but same result."""
        # Arrange
        record_path = tmp_path / "runs" / "run-1.json"
        _write_codegen_record(record_path, {"run_id": "run-1", "stages": []})
        run = _make_run(kind="codegen.run", pid=dead_pid, artifact_root=record_path)

        # Act
        result = reconcile_state(run)

        # Assert
        assert result == "interrupted"

    def test_reconcile_state_dead_pid_and_complete_record_returns_artifact_outcome(
        self, dead_pid: int, tmp_path: Path
    ) -> None:
        """Process gone but the record finished writing a decided outcome: report that
        outcome, not interrupted -- resumability must come from the artifact, not a guess."""
        # Arrange
        record_path = tmp_path / "runs" / "run-1.json"
        _write_codegen_record(record_path, {"run_id": "run-1", "outcome": "completed"})
        run = _make_run(kind="codegen.run", pid=dead_pid, artifact_root=record_path)

        # Act
        result = reconcile_state(run)

        # Assert
        assert result == "succeeded"

    def test_presented_state_terminal_job_state_returns_stored_state_unchanged(
        self, dead_pid: int, tmp_path: Path
    ) -> None:
        """A job the state machine already finished must be reported exactly as stored --
        reconciliation only applies to the stranded-`running` case, never to a terminal one.
        Proven by deliberately mismatching: the run's own artifacts would reconcile to
        `failed`, but the stored terminal state must win regardless."""
        # Arrange
        record_path = tmp_path / "runs" / "run-1.json"
        _write_codegen_record(record_path, {"run_id": "run-1", "outcome": "halted_at_ceiling"})
        run = _make_run(kind="codegen.run", pid=dead_pid, artifact_root=record_path)

        # Act
        result = presented_state("succeeded", run)

        # Assert
        assert result == "succeeded"


# Outcome mapping (data-model A3 / research.md) --------------------------------
# A real regression was caught in review here: an environment abort must never present
# as a success. Each of the four persisted `outcome` values is asserted individually so
# the mapping table cannot silently drift.


class TestCodegenOutcomeMapping:
    @pytest.mark.parametrize(
        ("recorded_outcome", "expected_state"),
        [
            pytest.param("completed", "succeeded", id="completed-is-success"),
            pytest.param(
                "rejected_at_gate", "cancelled", id="rejected-at-gate-is-a-decision-not-a-failure"
            ),
            pytest.param(
                "halted_at_ceiling", "failed", id="halted-at-ceiling-is-an-unrepaired-code-defect"
            ),
            pytest.param(
                "aborted_environment",
                "failed",
                id="aborted-environment-must-never-read-as-succeeded",
            ),
        ],
    )
    def test_reconcile_state_maps_each_persisted_outcome_to_its_presentation_state(
        self, dead_pid: int, tmp_path: Path, recorded_outcome: str, expected_state: str
    ) -> None:
        """Locks down the four-way outcome table; a broken .NET toolchain
        (`aborted_environment`) must present as `failed`, never `succeeded`."""
        # Arrange
        record_path = tmp_path / "runs" / f"{recorded_outcome}.json"
        _write_codegen_record(record_path, {"run_id": "run-1", "outcome": recorded_outcome})
        run = _make_run(kind="codegen.run", pid=dead_pid, artifact_root=record_path)

        # Act
        result = reconcile_state(run)

        # Assert
        assert result == expected_state


# T010 -- interrupted is a presentation state only ------------------------------


class TestInterruptedNeverPersisted:
    def test_finish_state_literal_has_no_interrupted_member(self) -> None:
        """`jobs.FinishState` must never grow an `interrupted` member -- the existing job
        state machine and its consumers are untouched by this feature (research.md R2)."""
        # Act
        members = get_args(jobs_module.FinishState)

        # Assert
        assert "interrupted" not in members

    def test_presented_state_reconciling_stranded_row_does_not_write_jobs_table(
        self, dead_pid: int, tmp_path: Path
    ) -> None:
        """Reconciling a stranded `running` row to `interrupted` must leave the `jobs`
        table's `state` column exactly as stored, and perform zero writes -- `interrupted`
        is derived at read time and never persisted (T010)."""
        # Arrange
        write_guard = WriteGuard()
        db_path = tmp_path / "webapi.sqlite3"
        storage = Storage(db_path, write_guard=write_guard)
        try:
            storage.save_job(
                {
                    "job_id": "job-1",
                    "kind": "codegen.run",
                    "state": "running",
                    "created_at": utc_now_iso(),
                }
            )
            record_path = tmp_path / "runs" / "run-1.json"
            run = _make_run(kind="codegen.run", pid=dead_pid, artifact_root=record_path, job_id="job-1")
            writes_before = write_guard.count

            # Act
            result = presented_state("running", run)

            # Assert
            assert result == "interrupted"
            assert write_guard.count == writes_before
            reloaded = storage.load_job("job-1")
            assert reloaded is not None
            assert reloaded["state"] == "running"
        finally:
            storage.close()


# T011 -- post-restart exclusive-resource liveness ------------------------------


class TestPostRestartResourceLiveness:
    def test_check_resource_liveness_dead_pid_clears_stale_row(
        self, storage: Storage, dead_pid: int, tmp_path: Path
    ) -> None:
        """A resource lock recorded before a restart, whose process has since died, must
        be cleared so a new run can take the resource -- the in-memory `JobManager`
        `_resources` lock does not survive a restart (research.md R7)."""
        # Arrange
        storage.save_supervised_run(
            {
                "exclusive_resource": "codegen",
                "job_id": "job-1",
                "kind": "codegen.run",
                "run_id": "run-1",
                "pid": dead_pid,
                "artifact_root": str(tmp_path / "runs" / "run-1.json"),
                "created_at": utc_now_iso(),
            }
        )

        # Act
        result = check_resource_liveness("codegen", storage=storage)

        # Assert
        assert result is None
        assert storage.load_supervised_run("codegen") is None

    def test_check_resource_liveness_alive_pid_keeps_resource_held(
        self, storage: Storage, alive_pid: int, tmp_path: Path
    ) -> None:
        """A detached run still alive after a restart must keep its resource held, so a
        second launch for the same module correctly races against reality rather than a
        forgotten in-memory lock."""
        # Arrange
        storage.save_supervised_run(
            {
                "exclusive_resource": "evals",
                "job_id": "job-2",
                "kind": "evals.matrix",
                "run_id": "run-2",
                "pid": alive_pid,
                "artifact_root": str(tmp_path / "evals" / "run-2"),
                "created_at": utc_now_iso(),
            }
        )

        # Act
        result = check_resource_liveness("evals", storage=storage)

        # Assert
        assert result is not None
        assert result.pid == alive_pid
        assert storage.load_supervised_run("evals") is not None


# T009 -- evals reconciliation reuses the subsystem's own cell-completion rule --


class TestEvalsMatrixReconciliation:
    def test_reconcile_state_dead_pid_and_missing_cell_directory_returns_interrupted(
        self, dead_pid: int, tmp_path: Path
    ) -> None:
        """A matrix with a cell directory the manifest promised but that was never
        written (the candidate cell never ran before the backend died) is incomplete --
        `is_cell_complete` is the subsystem's own resume rule, reused rather than
        reimplemented (research.md R2, data-model A5)."""
        # Arrange
        run_dir = tmp_path / "evals" / "run-3"
        _write_evals_manifest(run_dir, tasks=["task-a"], runs=1)
        _write_cell_metrics(run_dir, task_id="task-a", profile_name="baseline", repetition=1)
        # The candidate cell's metrics.json is deliberately never written.
        run = _make_run(
            kind="evals.matrix", pid=dead_pid, artifact_root=run_dir, exclusive_resource="evals"
        )

        # Act
        result = reconcile_state(run)

        # Assert
        assert result == "interrupted"

    def test_reconcile_state_dead_pid_and_every_promised_cell_complete_returns_succeeded(
        self, dead_pid: int, tmp_path: Path
    ) -> None:
        """Every cell the manifest promised has a parseable metrics.json: the matrix is
        complete and reconciles to succeeded, matching `cabal.evals.matrix.is_cell_complete`."""
        # Arrange
        run_dir = tmp_path / "evals" / "run-4"
        _write_evals_manifest(run_dir, tasks=["task-a"], runs=1)
        _write_cell_metrics(run_dir, task_id="task-a", profile_name="baseline", repetition=1)
        _write_cell_metrics(run_dir, task_id="task-a", profile_name="candidate", repetition=1)
        run = _make_run(
            kind="evals.matrix", pid=dead_pid, artifact_root=run_dir, exclusive_resource="evals"
        )

        # Act
        result = reconcile_state(run)

        # Assert
        assert result == "succeeded"


# T014 -- availability probes keep no_benchmark_tree and definitions_invalid distinct --


class TestEvalsAvailabilityProbes:
    def test_probe_evals_availability_no_evals_directory_returns_no_benchmark_tree(
        self, tmp_path: Path
    ) -> None:
        """No `evals/` directory at all is a setup state with a next step, not an error."""
        # Arrange
        project = tmp_path / "project"
        project.mkdir()

        # Act
        result = probe_evals_availability(project)

        # Assert
        assert result.available is False
        assert result.reason == "no_benchmark_tree"

    def test_probe_evals_availability_invalid_definitions_returns_definitions_invalid(
        self, tmp_path: Path
    ) -> None:
        """An `evals/` directory that exists but fails validation is an error blocking
        launch (FR-031) -- distinct from the no-tree-yet setup state above."""
        # Arrange
        project = tmp_path / "project"
        evals_root = project / "evals"
        evals_root.mkdir(parents=True)
        (evals_root / "eval.config.toml").write_text("runs_per_cell = 0\n", encoding="utf-8")

        # Act
        result = probe_evals_availability(project)

        # Assert
        assert result.available is False
        assert result.reason == "definitions_invalid"

    def test_probe_evals_availability_no_benchmark_tree_and_definitions_invalid_are_distinct_reasons(
        self, tmp_path: Path
    ) -> None:
        """The two failure reasons must never collapse into one another."""
        # Arrange
        no_tree_project = tmp_path / "no-tree-project"
        no_tree_project.mkdir()
        invalid_project = tmp_path / "invalid-project"
        evals_root = invalid_project / "evals"
        evals_root.mkdir(parents=True)
        (evals_root / "eval.config.toml").write_text("runs_per_cell = 0\n", encoding="utf-8")

        # Act
        no_tree_result = probe_evals_availability(no_tree_project)
        invalid_result = probe_evals_availability(invalid_project)

        # Assert
        assert no_tree_result.reason != invalid_result.reason
