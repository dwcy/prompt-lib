"""Unit tests for cabal.dashboard_git_service.collect_git — local git state collector.

Stubs the service's seams (shutil.which + subprocess.run) so no real git is invoked.
Covers NO_CLI, NOT_LINKED, OK (branches/remotes), and detached-HEAD branches.
"""

from __future__ import annotations

import subprocess

import pytest

from cabal import dashboard_git_service
from cabal.dashboard_git_service import collect_git
from cabal.models.dashboard import AvailabilityState


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=""
    )


def _make_dispatcher(responses):
    def fake_run(argv, *args, **kwargs):
        tail = tuple(argv[3:])
        for key, result in responses.items():
            if tail[: len(key)] == key:
                return result
        return _completed("")

    return fake_run


@pytest.fixture
def stub_git(monkeypatch):
    monkeypatch.setattr(
        dashboard_git_service.shutil, "which", lambda _name: "/usr/bin/git"
    )

    def _install(responses):
        monkeypatch.setattr(
            dashboard_git_service.subprocess, "run", _make_dispatcher(responses)
        )

    return _install


def test_collect_git_no_cli_returns_no_cli_state(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard_git_service.shutil, "which", lambda _name: None)

    section = collect_git(tmp_path)

    assert section.state == AvailabilityState.NO_CLI


def test_collect_git_not_a_repo_returns_not_linked(stub_git, tmp_path):
    stub_git({("rev-parse", "--is-inside-work-tree"): _completed("", returncode=128)})

    section = collect_git(tmp_path)

    assert section.state == AvailabilityState.NOT_LINKED


def test_collect_git_normal_repo_returns_ok(stub_git, tmp_path):
    stub_git(
        {
            ("rev-parse", "--is-inside-work-tree"): _completed("true\n"),
            ("rev-parse", "--abbrev-ref", "HEAD"): _completed("main\n"),
            ("branch",): _completed("main\nfeature/x\n"),
            ("remote", "-v"): _completed(
                "origin\thttps://github.com/o/r.git (fetch)\n"
                "origin\thttps://github.com/o/r.git (push)\n"
            ),
        }
    )

    section = collect_git(tmp_path)

    assert section.state == AvailabilityState.OK


def test_collect_git_normal_repo_reports_current_branch(stub_git, tmp_path):
    stub_git(
        {
            ("rev-parse", "--is-inside-work-tree"): _completed("true\n"),
            ("rev-parse", "--abbrev-ref", "HEAD"): _completed("main\n"),
            ("branch",): _completed("main\nfeature/x\n"),
            ("remote", "-v"): _completed(""),
        }
    )

    section = collect_git(tmp_path)

    assert section.current_branch == "main"


def test_collect_git_normal_repo_is_not_detached(stub_git, tmp_path):
    stub_git(
        {
            ("rev-parse", "--is-inside-work-tree"): _completed("true\n"),
            ("rev-parse", "--abbrev-ref", "HEAD"): _completed("main\n"),
            ("branch",): _completed("main\nfeature/x\n"),
            ("remote", "-v"): _completed(""),
        }
    )

    section = collect_git(tmp_path)

    assert section.detached is False


def test_collect_git_normal_repo_lists_two_local_branches(stub_git, tmp_path):
    stub_git(
        {
            ("rev-parse", "--is-inside-work-tree"): _completed("true\n"),
            ("rev-parse", "--abbrev-ref", "HEAD"): _completed("main\n"),
            ("branch",): _completed("main\nfeature/x\n"),
            ("remote", "-v"): _completed(""),
        }
    )

    section = collect_git(tmp_path)

    assert section.local_branches == ["main", "feature/x"]


def test_collect_git_normal_repo_marks_github_remote(stub_git, tmp_path):
    stub_git(
        {
            ("rev-parse", "--is-inside-work-tree"): _completed("true\n"),
            ("rev-parse", "--abbrev-ref", "HEAD"): _completed("main\n"),
            ("branch",): _completed("main\nfeature/x\n"),
            ("remote", "-v"): _completed(
                "origin\thttps://github.com/o/r.git (fetch)\n"
                "origin\thttps://github.com/o/r.git (push)\n"
            ),
        }
    )

    section = collect_git(tmp_path)

    assert len(section.remotes) == 1 and section.remotes[0].is_github is True


def test_collect_git_detached_head_sets_detached(stub_git, tmp_path):
    stub_git(
        {
            ("rev-parse", "--is-inside-work-tree"): _completed("true\n"),
            ("rev-parse", "--abbrev-ref", "HEAD"): _completed("HEAD\n"),
            ("rev-parse", "--short", "HEAD"): _completed("abc1234\n"),
            ("branch",): _completed("main\n"),
            ("remote", "-v"): _completed(""),
        }
    )

    section = collect_git(tmp_path)

    assert section.detached is True


def test_collect_git_detached_head_reports_short_sha_as_branch(stub_git, tmp_path):
    stub_git(
        {
            ("rev-parse", "--is-inside-work-tree"): _completed("true\n"),
            ("rev-parse", "--abbrev-ref", "HEAD"): _completed("HEAD\n"),
            ("rev-parse", "--short", "HEAD"): _completed("abc1234\n"),
            ("branch",): _completed("main\n"),
            ("remote", "-v"): _completed(""),
        }
    )

    section = collect_git(tmp_path)

    assert section.current_branch == "abc1234"


def test_collect_git_subprocess_timeout_returns_timeout_state(monkeypatch, tmp_path):
    monkeypatch.setattr(
        dashboard_git_service.shutil, "which", lambda _name: "/usr/bin/git"
    )

    def fake_run(argv, *args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=10)

    monkeypatch.setattr(dashboard_git_service.subprocess, "run", fake_run)

    section = collect_git(tmp_path)

    assert section.state == AvailabilityState.TIMEOUT


def test_collect_git_os_error_returns_error_state(monkeypatch, tmp_path):
    monkeypatch.setattr(
        dashboard_git_service.shutil, "which", lambda _name: "/usr/bin/git"
    )

    def fake_run(argv, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(dashboard_git_service.subprocess, "run", fake_run)

    section = collect_git(tmp_path)

    assert section.state == AvailabilityState.ERROR


def test_collect_git_os_error_hint_carries_message(monkeypatch, tmp_path):
    monkeypatch.setattr(
        dashboard_git_service.shutil, "which", lambda _name: "/usr/bin/git"
    )

    def fake_run(argv, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(dashboard_git_service.subprocess, "run", fake_run)

    section = collect_git(tmp_path)

    assert "boom" in section.hint
