# > 500 LoC justified: one Constitution Gate 3 contract-test suite pinning every clause of
# contracts/evals-api.md (T030) in one reviewable pass; splitting would fragment a single
# contract's test-first evidence across files a reviewer must then cross-reference by hand.
# -*- coding: utf-8 -*-
"""Contract tests (T030) for specs/021-codegen-eval-modules/contracts/evals-api.md.

Every read here goes through Group A artifacts `cabal.evals` already owns and already
implements for real (data-model.md): `matrix.py`'s run manifest/cell metrics, `judge.py`'s
comparison verdicts, and `report.py`'s own reducer (`build_report`, already implemented and
covered by its own tests -- this suite exercises the *webapi read surface* over it, never a
second, re-derived aggregation). Fixtures are built with those modules' real dataclasses and
`write_json_atomic`, never a mocked filesystem, so a passing test proves the webapi surface reads
exactly what `python -m cabal.evals report` would also read.

Every read route and every action currently raises `NotWiredError` (404 `not_wired`,
T031-T034/T042-T066), so almost every test below is expected to FAIL today at its first
behavioural assertion. That is Constitution Gate 3.

One field name in this suite is this test's own choice, not a pinned schema key: FR-039 requires
the payload to report "how many pairs were excluded and why" but no contract or schema artifact
names the key. This suite asserts `excluded_pairs: {"total", "tie", "judge_error"}` alongside the
`pairwise_win_rate` metric row -- a name chosen to mirror the sibling `failures` list `report.py`
already uses for the analogous task_pass_rate visibility requirement (FR-040). If T032/T034 land
with a different key, only that one assertion needs updating; the underlying requirement (the
exclusion must be visible, not silently netted out) does not change.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from cabal.evals import judge as evals_judge
from cabal.evals import matrix as evals_matrix
from cabal.evals.adapters.base import AdapterCapabilities
from cabal.evals.checks import CheckResult
from cabal.evals.metrics import TranscriptMetrics, build_metrics
from cabal.evals.worktree import DiffResult

from .webapi_fixtures import (
    app_factory,
    auth_headers,
    build_client,
    register_fixture_actions,
)

__all__ = ["app_factory"]

_CAPS_FULL = AdapterCapabilities(tokens=True, tool_calls=True, cost=True)


# --------------------------------------------------------------------------- fixtures/helpers ---


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "workspace"
    project.mkdir(parents=True)
    return project


def _evals_root(project: Path) -> Path:
    root = project / "evals"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_profile(evals_root: Path, name: str, *, env: dict[str, str]) -> Path:
    configs_dir = evals_root / "configs" / name
    configs_dir.mkdir(parents=True, exist_ok=True)
    env_lines = "\n".join(f'{key} = "{value}"' for key, value in env.items())
    (configs_dir / "profile.toml").write_text(
        f'description = "profile {name}"\n\n[env]\n{env_lines}\n', encoding="utf-8"
    )
    return configs_dir / "profile.toml"


def _write_invalid_task_missing_title(evals_root: Path, task_id: str) -> Path:
    task_dir = evals_root / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    path = task_dir / "task.toml"
    path.write_text('repo = "does-not-matter"\nref = "does-not-matter"\n', encoding="utf-8")
    return path


def _completed_cell(
    *,
    run_id: str,
    task_id: str,
    config_name: str,
    repetition: int,
    checks: tuple[CheckResult, ...] = (),
    tool_calls: int = 10,
    wall_seconds: float = 1.0,
) -> dict:
    return build_metrics(
        run_id=run_id,
        task_id=task_id,
        config_name=config_name,
        repetition=repetition,
        adapter_name="claude-code",
        status="completed",
        failure_reason=None,
        wall_seconds=wall_seconds,
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:01:00Z",
        capabilities=_CAPS_FULL,
        transcript=TranscriptMetrics(
            tool_calls_total=tool_calls, input_tokens=1000, output_tokens=200, cost_usd=0.01
        ),
        diff=DiffResult(patch_text="", changed_files=("a.cs",), insertions=1, deletions=0, empty_diff=False),
        expected_files=["a.cs"],
        checks=checks,
    )


def _failed_cell(*, run_id: str, task_id: str, config_name: str, repetition: int, reason: str) -> dict:
    payload = build_metrics(
        run_id=run_id,
        task_id=task_id,
        config_name=config_name,
        repetition=repetition,
        adapter_name="claude-code",
        status="failed",
        failure_reason=reason,
        wall_seconds=0.5,
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:30Z",
        capabilities=_CAPS_FULL,
        transcript=TranscriptMetrics(),
        diff=None,
        expected_files=["a.cs"],
        checks=(),
    )
    return payload


def _write_cell(run_dir: Path, task_id: str, config_name: str, repetition: int, payload: dict) -> Path:
    cell_dir = run_dir / task_id / config_name / str(repetition)
    cell_dir.mkdir(parents=True, exist_ok=True)
    path = cell_dir / evals_matrix.METRICS_FILENAME
    evals_matrix.write_json_atomic(path, payload)
    return path


def _write_manifest(
    project: Path, run_id: str, *, tasks: list[str], baseline: str, candidate: str, runs: int
) -> Path:
    results_dir = project / "evals" / "results"
    run_dir = results_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / evals_matrix.MANIFEST_FILENAME
    evals_matrix.write_json_atomic(
        path,
        {
            "run_id": run_id,
            "baseline": baseline,
            "candidate": candidate,
            "runs": runs,
            "tasks": tasks,
            "adapter": "claude-code",
            "created_at": "2026-01-01T00:00:00Z",
        },
    )
    return run_dir


def _write_comparison(
    run_dir: Path, task_id: str, *, baseline: str, candidate: str, pairs: list[dict]
) -> Path:
    task_dir = run_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    path = task_dir / evals_judge.COMPARISON_FILENAME
    evals_matrix.write_json_atomic(
        path,
        {
            "run_id": run_dir.name,
            "task_id": task_id,
            "baseline_config": baseline,
            "candidate_config": candidate,
            "judge_model": "claude-haiku",
            "rubrics": [],
            "pairs": pairs,
        },
    )
    return path


def _pair(repetition: int, winner: str, order_agreement: bool) -> dict:
    return {
        "repetition": repetition,
        "winner": winner,
        "confidence": 0.8 if winner in {"baseline", "candidate"} and order_agreement else None,
        "order_agreement": order_agreement,
        "criteria": [],
        "truncated": False,
        "error_detail": None if winner != "judge_error" else "judge call failed",
    }


def _save_supervised_evals_run(app, *, job_id: str, run_id: str, pid: int, artifact_root: Path) -> None:
    app.state.storage.save_supervised_run(
        {
            "exclusive_resource": "evals",
            "job_id": job_id,
            "kind": "evals.matrix",
            "run_id": run_id,
            "pid": pid,
            "artifact_root": str(artifact_root),
            "created_at": "2026-01-01T00:00:00Z",
        }
    )


# --------------------------------------------------------------------------------- availability ---


def test_availability_no_benchmark_tree_and_definitions_invalid_are_distinct_values(
    app_factory, tmp_path
) -> None:
    """data-model B3: 'no_benchmark_tree (a setup state) and definitions_invalid (an error) are
    distinct values and must never be collapsed.'"""
    no_tree_project = _project(tmp_path / "no-tree")
    app, client = build_client(app_factory, project=no_tree_project)
    no_tree = client.get("/api/evals/availability", headers=auth_headers())
    assert no_tree.status_code != 500, no_tree.text
    assert no_tree.status_code == 200, no_tree.text
    assert no_tree.json()["data"]["reason"] == "no_benchmark_tree"

    broken_project = _project(tmp_path / "broken-tree")
    broken_root = _evals_root(broken_project)
    _write_invalid_task_missing_title(broken_root, "broken-task")
    app2, client2 = build_client(app_factory, project=broken_project)
    broken = client2.get("/api/evals/availability", headers=auth_headers())
    assert broken.status_code != 500, broken.text
    assert broken.status_code == 200, broken.text
    assert broken.json()["data"]["reason"] == "definitions_invalid"
    assert broken.json()["data"]["reason"] != no_tree.json()["data"]["reason"]


# ---------------------------------------------------------------------------------- definitions ---


def test_definitions_listing_reports_editable_and_uncommitted_per_entry(app_factory, tmp_path) -> None:
    """FR-055/research.md R6: every definition entry must report both `editable` (false when the
    file cannot be represented faithfully) and `uncommitted` (the tree is version-controlled; an
    uncommitted task is not yet a reproducible benchmark)."""
    project = _project(tmp_path)
    evals_root = _evals_root(project)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    _write_profile(evals_root, "baseline", env={"MODE": "control"})

    app, client = build_client(app_factory, project=project)
    response = client.get("/api/evals/definitions", headers=auth_headers())

    assert response.status_code == 200, response.text
    entries = response.json()["data"]["definitions"]
    assert entries, "expected at least the one profile entry"
    for entry in entries:
        assert isinstance(entry.get("editable"), bool)
        assert isinstance(entry.get("uncommitted"), bool)
    profile_entries = [e for e in entries if "baseline" in e.get("path", "")]
    assert profile_entries and all(e["uncommitted"] is True for e in profile_entries), (
        "a never-committed file under a git-tracked evals/ must report uncommitted: true"
    )


def test_definitions_validate_reports_file_and_locating_detail_and_success_counts(
    app_factory, tmp_path
) -> None:
    """FR-030/SC-006: each problem carries the file and enough detail to fix it on the first
    attempt; success reports counts of what was found (US5 scenario 1)."""
    broken_project = _project(tmp_path / "broken")
    broken_root = _evals_root(broken_project)
    _write_invalid_task_missing_title(broken_root, "broken-task")
    app, client = build_client(app_factory, project=broken_project)

    invalid = client.get("/api/evals/definitions/validate", headers=auth_headers())
    assert invalid.status_code == 200, invalid.text
    problems = invalid.json()["data"]["problems"]
    assert problems, "a task missing its required title must be reported"
    problem = problems[0]
    assert "task.toml" in problem["file"]
    assert problem.get("field") or problem.get("message")

    valid_project = _project(tmp_path / "valid")
    valid_root = _evals_root(valid_project)
    _write_profile(valid_root, "baseline", env={"MODE": "control"})
    _write_profile(valid_root, "candidate", env={"MODE": "treatment"})
    app2, client2 = build_client(app_factory, project=valid_project)

    valid = client2.get("/api/evals/definitions/validate", headers=auth_headers())
    assert valid.status_code == 200, valid.text
    data = valid.json()["data"]
    assert data["problems"] == []
    assert data["tasks"] == 0
    assert data["profiles"] == 2


# ---------------------------------------------------------------------------------- runs listing ---


def test_runs_listing_includes_cli_produced_run_with_complete_artifacts_as_succeeded(
    app_factory, tmp_path
) -> None:
    """FR-045/research.md R1: 'there is no launched here flag, because there is no separate code
    path' -- a run this backend never tracked a pid for must still list, reconciled from its own
    complete artifact tree alone."""
    project = _project(tmp_path)
    run_dir = _write_manifest(
        project, "evalrun-cli-only", tasks=["demo-task"], baseline="control", candidate="treatment", runs=1,
    )
    for config in ("control", "treatment"):
        _write_cell(
            run_dir,
            "demo-task",
            config,
            1,
            _completed_cell(run_id="evalrun-cli-only", task_id="demo-task", config_name=config, repetition=1),
        )

    app, client = build_client(app_factory, project=project)
    response = client.get("/api/evals/runs", headers=auth_headers())

    assert response.status_code == 200, response.text
    runs = response.json()["data"]["runs"]
    matching = [r for r in runs if r.get("run_id") == "evalrun-cli-only"]
    assert matching, "a run this backend never launched must still appear in the listing"
    assert matching[0]["state"] == "succeeded"


def test_runs_listing_marks_partially_written_run_readable_false_without_breaking_listing(
    app_factory, tmp_path
) -> None:
    """contract: 'A partially written run directory yields a readable: false entry rather than
    breaking the listing.'"""
    project = _project(tmp_path)
    good_dir = _write_manifest(
        project, "evalrun-good", tasks=["demo-task"], baseline="control", candidate="treatment", runs=1
    )
    _write_cell(
        good_dir, "demo-task", "control", 1,
        _completed_cell(run_id="evalrun-good", task_id="demo-task", config_name="control", repetition=1),
    )
    _write_cell(
        good_dir, "demo-task", "treatment", 1,
        _completed_cell(run_id="evalrun-good", task_id="demo-task", config_name="treatment", repetition=1),
    )
    broken_dir = project / "evals" / "results" / "evalrun-broken"
    broken_dir.mkdir(parents=True)
    (broken_dir / evals_matrix.MANIFEST_FILENAME).write_text("{not valid json", encoding="utf-8")

    app, client = build_client(app_factory, project=project)
    response = client.get("/api/evals/runs", headers=auth_headers())

    assert response.status_code == 200, response.text
    runs = response.json()["data"]["runs"]
    by_id = {r["run_id"]: r for r in runs}
    assert "evalrun-good" in by_id and by_id["evalrun-good"].get("readable", True) is not False
    assert "evalrun-broken" in by_id
    assert by_id["evalrun-broken"].get("readable") is False
    assert by_id["evalrun-broken"].get("error")


def test_runs_listing_interrupted_state_and_resumable_come_from_the_manifest_not_a_job_row(
    app_factory, tmp_path
) -> None:
    """research.md R2: process gone + incomplete artifacts -> interrupted; `resumable` must be
    derived from the manifest (never a job record) -- proven by two runs with no tracked pid at
    all, one with a valid manifest (resumable) and one with a corrupt one (not resumable)."""
    project = _project(tmp_path)
    resumable_dir = _write_manifest(
        project, "evalrun-resumable", tasks=["demo-task"], baseline="control", candidate="treatment", runs=1
    )
    _write_cell(
        resumable_dir, "demo-task", "control", 1,
        _completed_cell(run_id="evalrun-resumable", task_id="demo-task", config_name="control", repetition=1),
    )
    # "treatment" cell never completes -> the matrix this manifest promised is incomplete.

    not_resumable_dir = project / "evals" / "results" / "evalrun-not-resumable"
    not_resumable_dir.mkdir(parents=True)
    (not_resumable_dir / evals_matrix.MANIFEST_FILENAME).write_text('{"run_id": "x"}', encoding="utf-8")

    app, client = build_client(app_factory, project=project)
    response = client.get("/api/evals/runs", headers=auth_headers())

    assert response.status_code == 200, response.text
    by_id = {r["run_id"]: r for r in response.json()["data"]["runs"]}
    assert by_id["evalrun-resumable"]["state"] == "interrupted"
    assert by_id["evalrun-resumable"]["resumable"] is True
    if by_id["evalrun-not-resumable"].get("readable", True) is not False:
        assert by_id["evalrun-not-resumable"]["state"] == "interrupted"
        assert by_id["evalrun-not-resumable"]["resumable"] is False


def test_runs_listing_reports_running_only_for_the_run_its_own_tracked_pid_is_alive(
    app_factory, tmp_path
) -> None:
    """data-model B1: reconciliation is per-run-id against ITS OWN supervised handle -- a second,
    untracked incomplete run must not inherit 'running' from an unrelated live process."""
    project = _project(tmp_path)
    live_dir = _write_manifest(
        project, "evalrun-live", tasks=["demo-task"], baseline="control", candidate="treatment", runs=1
    )
    untracked_dir = _write_manifest(
        project, "evalrun-untracked", tasks=["demo-task"], baseline="control", candidate="treatment", runs=1
    )

    app, client = build_client(app_factory, project=project)
    process = subprocess.Popen(
        ["python", "-c", "import time; time.sleep(20)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _save_supervised_evals_run(
            app, job_id="job-live", run_id="evalrun-live", pid=process.pid, artifact_root=live_dir
        )
        response = client.get("/api/evals/runs", headers=auth_headers())
        assert response.status_code == 200, response.text
        by_id = {r["run_id"]: r for r in response.json()["data"]["runs"]}
        assert by_id["evalrun-live"]["state"] == "running"
        assert by_id["evalrun-untracked"]["state"] == "interrupted"
    finally:
        process.terminate()
        process.wait(timeout=5)


# -------------------------------------------------------------------------------------- report ---


def test_report_stddev_absent_below_three_samples_present_at_three(app_factory, tmp_path) -> None:
    """FR-041: 'stddev is absent for n < 3 - not zero, not null-rendered-as-zero.' `control` gets
    two quality samples (its third cell fails outright and is excluded from the mean per FR-040),
    `treatment` gets three -- proving both branches from one run."""
    project = _project(tmp_path)
    run_dir = _write_manifest(
        project, "evalrun-stddev", tasks=["demo-task"], baseline="control", candidate="treatment", runs=3
    )
    build_check = CheckResult(kind="build", cmd=["dotnet", "build"], status="passed", exit_code=0, passed_count=None, failed_count=None, duration_seconds=5.0)
    for rep in (1, 2):
        _write_cell(
            run_dir, "demo-task", "control", rep,
            _completed_cell(run_id="evalrun-stddev", task_id="demo-task", config_name="control", repetition=rep, checks=(build_check,)),
        )
    _write_cell(
        run_dir, "demo-task", "control", 3,
        _failed_cell(run_id="evalrun-stddev", task_id="demo-task", config_name="control", repetition=3, reason="adapter_unavailable"),
    )
    for rep in (1, 2, 3):
        _write_cell(
            run_dir, "demo-task", "treatment", rep,
            _completed_cell(run_id="evalrun-stddev", task_id="demo-task", config_name="treatment", repetition=rep, checks=(build_check,)),
        )

    app, client = build_client(app_factory, project=project)
    response = client.get("/api/evals/runs/evalrun-stddev/report", headers=auth_headers())

    assert response.status_code == 200, response.text
    rows = {row["metric"]: row for row in response.json()["data"]["metrics_rows"]}
    build_row = rows["build_success_rate"]
    assert build_row["per_config"]["control"]["n"] == 2
    assert build_row["per_config"]["control"]["stddev"] is None, "n=2 must not report a spread"
    assert build_row["per_config"]["treatment"]["n"] == 3
    assert build_row["per_config"]["treatment"]["stddev"] is not None, "n=3 must report a spread"

    task_pass_row = rows["task_pass_rate"]
    assert task_pass_row["per_config"]["control"]["n"] == 3, (
        "the failed cell still counts a sample against task_pass_rate (FR-040)"
    )
    assert task_pass_row["per_config"]["control"]["mean"] == pytest.approx(2 / 3)
    failures = response.json()["data"]["failures"]
    assert any(f["config_name"] == "control" and f["repetition"] == 3 for f in failures), (
        "the exclusion from the quality mean must be visible, not just netted into a lower rate"
    )


def test_report_pairwise_win_rate_excludes_ties_and_judge_errors_and_reports_the_exclusion(
    app_factory, tmp_path
) -> None:
    """FR-038/FR-039: order_agreement:false must read as a tie, never a win; ties and judge errors
    must be excluded from the rate, and the payload must say how many were excluded and why."""
    project = _project(tmp_path)
    run_dir = _write_manifest(
        project, "evalrun-pairwise", tasks=["demo-task"], baseline="control", candidate="treatment", runs=3
    )
    for rep in (1, 2, 3):
        for config in ("control", "treatment"):
            _write_cell(
                run_dir, "demo-task", config, rep,
                _completed_cell(run_id="evalrun-pairwise", task_id="demo-task", config_name=config, repetition=rep),
            )
    _write_comparison(
        run_dir,
        "demo-task",
        baseline="control",
        candidate="treatment",
        pairs=[
            _pair(1, "candidate", True),
            _pair(2, "tie", False),  # order disagreement -> tie, never a win (FR-038)
            _pair(3, "judge_error", False),
        ],
    )

    app, client = build_client(app_factory, project=project)
    response = client.get("/api/evals/runs/evalrun-pairwise/report", headers=auth_headers())

    assert response.status_code == 200, response.text
    rows = {row["metric"]: row for row in response.json()["data"]["metrics_rows"]}
    win_row = rows["pairwise_win_rate"]
    assert win_row["per_config"]["treatment"]["n"] == 1, "only the one decisive pair counts"
    assert win_row["per_config"]["control"]["n"] == 1
    assert win_row["per_config"]["treatment"]["mean"] == 1.0
    assert win_row["per_config"]["control"]["mean"] == 0.0

    excluded = win_row.get("excluded_pairs")
    assert excluded is not None, "FR-039: the exclusion must be visible, not silently netted out"
    assert excluded["total"] == 2
    assert excluded["tie"] == 1
    assert excluded["judge_error"] == 1


def test_report_deterministic_half_still_returns_when_judge_results_are_absent(app_factory, tmp_path) -> None:
    """FR-043: 'a missing judge degrades the payload, it does not empty it.'"""
    project = _project(tmp_path)
    run_dir = _write_manifest(
        project, "evalrun-no-judge", tasks=["demo-task"], baseline="control", candidate="treatment", runs=1
    )
    for config in ("control", "treatment"):
        _write_cell(
            run_dir, "demo-task", config, 1,
            _completed_cell(run_id="evalrun-no-judge", task_id="demo-task", config_name=config, repetition=1),
        )
    # No comparison.json is ever written for this task.

    app, client = build_client(app_factory, project=project)
    response = client.get("/api/evals/runs/evalrun-no-judge/report", headers=auth_headers())

    assert response.status_code == 200, response.text
    rows = {row["metric"]: row for row in response.json()["data"]["metrics_rows"]}
    assert rows["task_pass_rate"]["per_config"]["control"]["n"] == 1
    win_row = rows["pairwise_win_rate"]
    assert win_row["per_config"]["control"]["n"] == 0


def test_report_every_aggregate_carries_its_sample_count_n(app_factory, tmp_path) -> None:
    """SC-009: every displayed aggregate carries its `n`."""
    project = _project(tmp_path)
    run_dir = _write_manifest(
        project, "evalrun-n-check", tasks=["demo-task"], baseline="control", candidate="treatment", runs=1
    )
    for config in ("control", "treatment"):
        _write_cell(
            run_dir, "demo-task", config, 1,
            _completed_cell(run_id="evalrun-n-check", task_id="demo-task", config_name=config, repetition=1),
        )

    app, client = build_client(app_factory, project=project)
    response = client.get("/api/evals/runs/evalrun-n-check/report", headers=auth_headers())

    assert response.status_code == 200, response.text
    for row in response.json()["data"]["metrics_rows"]:
        for config_stats in row["per_config"].values():
            assert "n" in config_stats


# ------------------------------------------------------------------------------------ cell detail ---


def test_cell_detail_reports_a_timed_out_check_as_a_result_never_an_error(app_factory, tmp_path) -> None:
    """data-model A6: 'a check outcome - including a timeout - is recorded data, never an
    exception'; the read surface must preserve that, not translate it into an HTTP error."""
    project = _project(tmp_path)
    run_dir = _write_manifest(
        project, "evalrun-timeout", tasks=["demo-task"], baseline="control", candidate="treatment", runs=1
    )
    timeout_check = CheckResult(
        kind="test", cmd=["pytest"], status="timeout", exit_code=None,
        passed_count=None, failed_count=None, duration_seconds=30.0,
    )
    _write_cell(
        run_dir, "demo-task", "control", 1,
        _completed_cell(
            run_id="evalrun-timeout", task_id="demo-task", config_name="control", repetition=1,
            checks=(timeout_check,),
        ),
    )

    app, client = build_client(app_factory, project=project)
    response = client.get(
        "/api/evals/runs/evalrun-timeout/cells/demo-task/control/1", headers=auth_headers()
    )

    assert response.status_code == 200, response.text
    checks = response.json()["data"]["checks"]
    assert any(check["status"] == "timeout" for check in checks), (
        "a timed-out check must be readable as its own status, not surfaced as an error"
    )


# ---------------------------------------------------------------------------------------- launch ---


def test_evals_launch_refused_409_when_definitions_invalid(app_factory, tmp_path) -> None:
    """FR-031: 'Refused with 409 definitions_invalid when the tree fails validation, returning
    the failures as the reason.'"""
    project = _project(tmp_path)
    broken_root = _evals_root(project)
    _write_invalid_task_missing_title(broken_root, "broken-task")
    _write_profile(broken_root, "control", env={"MODE": "control"})
    _write_profile(broken_root, "treatment", env={"MODE": "treatment"})

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    response = client.post(
        "/api/actions/evals.launch/prepare",
        json={"baseline": "control", "candidate": "treatment", "tasks": [], "runs": 1},
        headers=auth_headers(),
    )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "definitions_invalid"


def test_evals_launch_reports_the_isolated_config_directory(app_factory, tmp_path) -> None:
    """FR-034/SC-011: 'the response reports the isolated config directory the run will use, so
    the module can show that the user's real agent configuration was never touched.' Asserted at
    prepare time via the same `CLAUDE_CONFIG_DIR` vocabulary the claude-code adapter already uses
    (`AgentRunSpec.config_dir`), since `effect_preview.commands` is where a preview shows what will
    actually run."""
    project = _project(tmp_path)
    evals_root = _evals_root(project)
    _write_profile(evals_root, "control", env={"MODE": "control"})
    _write_profile(evals_root, "treatment", env={"MODE": "treatment"})

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    response = client.post(
        "/api/actions/evals.launch/prepare",
        json={"baseline": "control", "candidate": "treatment", "tasks": [], "runs": 1},
        headers=auth_headers(),
    )

    assert response.status_code == 200, response.text
    preview = response.json()["data"]["effect_preview"]
    assert "CLAUDE_CONFIG_DIR" in json.dumps(preview), (
        "the preview must show the user's own agent configuration is untouched"
    )


# ---------------------------------------------------------------------------------------- cancel ---


def test_evals_cancel_on_an_already_finished_run_is_idempotent_not_an_error(app_factory, tmp_path) -> None:
    """contract: 'Idempotent - cancelling a finished run is a no-op, not an error.'"""
    project = _project(tmp_path)
    run_dir = _write_manifest(
        project, "evalrun-finished", tasks=["demo-task"], baseline="control", candidate="treatment", runs=1
    )
    for config in ("control", "treatment"):
        _write_cell(
            run_dir, "demo-task", config, 1,
            _completed_cell(run_id="evalrun-finished", task_id="demo-task", config_name=config, repetition=1),
        )

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    prepared = client.post(
        "/api/actions/evals.cancel/prepare", json={"run_id": "evalrun-finished"}, headers=auth_headers()
    )
    assert prepared.status_code == 200, prepared.text
    executed = client.post(
        "/api/actions/evals.cancel/execute",
        json={"ticket_id": prepared.json()["data"]["ticket_id"]},
        headers=auth_headers(),
    )
    assert executed.status_code in {200, 202}, executed.text

    audit = client.get("/api/audit", headers=auth_headers())
    entries = audit.json()["data"]["entries"]
    assert any(e["action_id"] == "evals.cancel" for e in entries), "FR-006: cancel must be audited"


# --------------------------------------------------------------------------------- definitions ---


def test_definition_save_validates_before_writing_and_writes_nothing_on_refusal(
    app_factory, tmp_path
) -> None:
    """FR-052: 'Validated before writing; an invalid definition is refused with the specific
    problem and nothing is written.'"""
    project = _project(tmp_path)
    _evals_root(project)
    target = project / "evals" / "configs" / "new-profile" / "profile.toml"

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    response = client.post(
        "/api/actions/evals.definition_save/prepare",
        json={"path": "configs/new-profile/profile.toml", "content": {}},  # missing required description
        headers=auth_headers(),
    )

    assert response.status_code in {400, 422}, response.text
    assert not target.exists(), "an invalid definition must never be written to disk"


def test_definition_save_refuses_409_when_the_file_changed_externally_since_prepare(
    app_factory, tmp_path
) -> None:
    """FR-053: the precondition digest binds to the file's current content hash, so an edit
    landing between prepare and execute must refuse with `409 definition_changed_externally`
    rather than silently overwriting it."""
    project = _project(tmp_path)
    evals_root = _evals_root(project)
    path = _write_profile(evals_root, "control", env={"MODE": "control"})

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    prepared = client.post(
        "/api/actions/evals.definition_save/prepare",
        json={
            "path": "configs/control/profile.toml",
            "content": {"description": "profile control", "env": {"MODE": "changed-by-editor"}},
        },
        headers=auth_headers(),
    )
    assert prepared.status_code == 200, prepared.text

    path.write_text('description = "profile control"\n\n[env]\nMODE = "changed-on-disk"\n', encoding="utf-8")

    executed = client.post(
        "/api/actions/evals.definition_save/execute",
        json={"ticket_id": prepared.json()["data"]["ticket_id"]},
        headers=auth_headers(),
    )

    assert executed.status_code == 409, executed.text
    assert executed.json()["error"]["code"] == "definition_changed_externally"


def test_definition_delete_keeps_a_stored_run_that_referenced_it_readable(app_factory, tmp_path) -> None:
    """FR-054/data-model cross-cutting rule 5: a run is read against the manifest it recorded at
    launch, so deleting the definition it used must not break reading that run's report."""
    project = _project(tmp_path)
    evals_root = _evals_root(project)
    _write_profile(evals_root, "control", env={"MODE": "control"})
    _write_profile(evals_root, "treatment", env={"MODE": "treatment"})
    run_dir = _write_manifest(
        project, "evalrun-post-delete", tasks=["demo-task"], baseline="control", candidate="treatment", runs=1
    )
    for config in ("control", "treatment"):
        _write_cell(
            run_dir, "demo-task", config, 1,
            _completed_cell(run_id="evalrun-post-delete", task_id="demo-task", config_name=config, repetition=1),
        )

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    prepared = client.post(
        "/api/actions/evals.definition_delete/prepare",
        json={"path": "configs/control/profile.toml"},
        headers=auth_headers(),
    )
    assert prepared.status_code == 200, prepared.text
    executed = client.post(
        "/api/actions/evals.definition_delete/execute",
        json={"ticket_id": prepared.json()["data"]["ticket_id"]},
        headers=auth_headers(),
    )
    assert executed.status_code == 200, executed.text

    report = client.get("/api/evals/runs/evalrun-post-delete/report", headers=auth_headers())
    assert report.status_code == 200, (
        "a stored run must still render fully after its profile definition is deleted"
    )


# ----------------------------------------------------------------------------------- concurrency ---


def test_exclusive_resource_evals_is_separate_from_codegen(app_factory, tmp_path) -> None:
    """research.md R7: 'exclusive_resource: "evals" - separate from "codegen", so the two modules
    run independently.' A job holding "codegen" must never block a launch naming "evals"."""
    app, client = build_client(app_factory)
    register_fixture_actions(app)

    def _launch(resource: str):
        prepared = client.post(
            "/api/actions/test.job_emitter/prepare",
            json={"lines": 20, "delay_ms": 50, "exclusive_resource": resource},
            headers=auth_headers(),
        )
        return client.post(
            "/api/actions/test.job_emitter/execute",
            json={"ticket_id": prepared.json()["data"]["ticket_id"]},
            headers=auth_headers(),
        )

    codegen_job = _launch("codegen")
    assert codegen_job.status_code == 202, codegen_job.text

    evals_job = _launch("evals")
    assert evals_job.status_code == 202, (
        f"a live codegen job must never block an evals launch (separate resource namespaces): "
        f"{evals_job.text}"
    )

    second_evals_job = _launch("evals")
    assert second_evals_job.status_code == 409, second_evals_job.text
    assert second_evals_job.json()["error"]["code"] == "job_conflict"
    assert second_evals_job.json()["error"]["blocking_job_id"] == evals_job.json()["data"]["job_id"]
