"""Regression tests: an exclusive resource stays held until the runner really stops."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from cabal.webapi.jobs import JobConflict, JobManager
from cabal.webapi.storage import Storage


@pytest.fixture
def manager(tmp_path: Path) -> JobManager:
    return JobManager(Storage(tmp_path / "jobs.sqlite3"))


def test_cancelled_job_keeps_its_resource_until_the_runner_returns(
    manager: JobManager,
) -> None:
    started = threading.Event()
    release = threading.Event()

    def runner(handle) -> None:
        started.set()
        release.wait(timeout=5)
        handle.finish("cancelled")

    job = manager.create("test.blocking", runner=runner, exclusive_resource="shared")
    assert started.wait(timeout=5)
    manager.cancel(job.job_id)

    with pytest.raises(JobConflict):
        manager.create("test.blocking", runner=lambda handle: None, exclusive_resource="shared")

    release.set()


def test_resource_is_reusable_once_the_runner_has_finished(manager: JobManager) -> None:
    done = threading.Event()
    first = manager.create(
        "test.quick",
        runner=lambda handle: done.set(),
        exclusive_resource="shared",
    )
    assert done.wait(timeout=5)

    second = _create_when_free(manager, "shared")

    assert second.job_id != first.job_id


def _create_when_free(manager: JobManager, resource: str, timeout: float = 5.0):
    """Retry past the brief window between a runner's last statement and its release."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return manager.create(
                "test.quick", runner=lambda handle: None, exclusive_resource=resource
            )
        except JobConflict:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)
