"""Unit tests for the dashboard GitHub collector (US2).

Stubs the collector's seams so no real `gh`/network I/O is invoked. Covers
cabal.dashboard_github_service.collect_github across remote/CLI/auth/data paths.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from cabal import dashboard_github_service
from cabal.dashboard_github_service import collect_github
from cabal.gh_accounts import GhAccount
from cabal.models.dashboard import AvailabilityState, GitRemote


def _github_remote(name: str = "origin") -> GitRemote:
    return GitRemote(name=name, url="https://github.com/o/r.git", is_github=True)


def _non_github_remote(name: str = "gitlab") -> GitRemote:
    return GitRemote(name=name, url="https://gitlab.com/o/r.git", is_github=False)


def _authed_account() -> GhAccount:
    return GhAccount(
        user="octocat", host="github.com", active=True, valid=True, storage="keyring"
    )


def _invalid_account() -> GhAccount:
    return GhAccount(
        user="octocat", host="github.com", active=True, valid=False, storage="keyring"
    )


def _make_gh_dispatcher(runs_json: str = "[]", prs_json: str = "[]"):
    def fake_run_gh(args, stdin=None):
        if args[:2] == ["run", "list"]:
            return 0, runs_json
        if args[:2] == ["pr", "list"]:
            return 0, prs_json
        return 0, ""

    return fake_run_gh


@pytest.fixture
def stub_gh(monkeypatch):
    monkeypatch.setattr(
        dashboard_github_service.shutil, "which", lambda _name: "/usr/bin/gh"
    )
    monkeypatch.setattr(
        dashboard_github_service, "parse_auth_status", lambda _out: [_authed_account()]
    )

    def _install(run_gh):
        monkeypatch.setattr(dashboard_github_service, "_run_gh", run_gh)

    return _install


def test_collect_github_no_github_remote_returns_not_linked(tmp_path):
    section = collect_github(tmp_path, "main", [])

    assert section.state == AvailabilityState.NOT_LINKED


def test_collect_github_only_non_github_remote_returns_not_linked(tmp_path):
    section = collect_github(tmp_path, "main", [_non_github_remote()])

    assert section.state == AvailabilityState.NOT_LINKED


def test_collect_github_no_cli_returns_no_cli_state(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard_github_service.shutil, "which", lambda _name: None)

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.state == AvailabilityState.NO_CLI


def test_collect_github_no_cli_still_reports_owner_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard_github_service.shutil, "which", lambda _name: None)

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.owner_repo == "o/r"


def test_collect_github_no_cli_still_reports_remote_used(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard_github_service.shutil, "which", lambda _name: None)

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.remote_used == "origin"


def test_collect_github_invalid_account_returns_not_authed(monkeypatch, tmp_path):
    monkeypatch.setattr(
        dashboard_github_service.shutil, "which", lambda _name: "/usr/bin/gh"
    )
    monkeypatch.setattr(dashboard_github_service, "_run_gh", lambda *a, **k: (1, ""))
    monkeypatch.setattr(
        dashboard_github_service,
        "parse_auth_status",
        lambda _out: [_invalid_account()],
    )

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.state == AvailabilityState.NOT_AUTHED


def test_collect_github_no_accounts_returns_not_authed(monkeypatch, tmp_path):
    monkeypatch.setattr(
        dashboard_github_service.shutil, "which", lambda _name: "/usr/bin/gh"
    )
    monkeypatch.setattr(dashboard_github_service, "_run_gh", lambda *a, **k: (1, ""))
    monkeypatch.setattr(dashboard_github_service, "parse_auth_status", lambda _out: [])

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.state == AvailabilityState.NOT_AUTHED


def test_collect_github_ok_returns_ok_state(stub_gh, tmp_path):
    runs = json.dumps(
        [
            {
                "name": "CI",
                "headBranch": "main",
                "status": "completed",
                "conclusion": "success",
                "url": "https://x/1",
                "createdAt": "2026-06-01",
            }
        ]
    )
    prs = json.dumps(
        [
            {
                "number": 7,
                "title": "Add feature",
                "author": {"login": "octocat"},
                "url": "https://x/pr/7",
            }
        ]
    )
    stub_gh(_make_gh_dispatcher(runs_json=runs, prs_json=prs))

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.state == AvailabilityState.OK


def test_collect_github_ok_is_connected(stub_gh, tmp_path):
    stub_gh(_make_gh_dispatcher())

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.connected is True


def test_collect_github_ok_reports_owner_repo(stub_gh, tmp_path):
    stub_gh(_make_gh_dispatcher())

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.owner_repo == "o/r"


def test_collect_github_ok_reports_remote_used(stub_gh, tmp_path):
    stub_gh(_make_gh_dispatcher())

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.remote_used == "origin"


def test_collect_github_ok_parses_run_count(stub_gh, tmp_path):
    runs = json.dumps(
        [
            {
                "name": "CI",
                "headBranch": "main",
                "status": "completed",
                "conclusion": "success",
                "url": "https://x/1",
                "createdAt": "2026-06-01",
            },
            {
                "name": "Lint",
                "headBranch": "main",
                "status": "completed",
                "conclusion": "failure",
                "url": "https://x/2",
                "createdAt": "2026-06-02",
            },
        ]
    )
    stub_gh(_make_gh_dispatcher(runs_json=runs))

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert len(section.runs) == 2


def test_collect_github_ok_parses_run_conclusion(stub_gh, tmp_path):
    runs = json.dumps(
        [
            {
                "name": "CI",
                "headBranch": "main",
                "status": "completed",
                "conclusion": "success",
                "url": "https://x/1",
                "createdAt": "2026-06-01",
            }
        ]
    )
    stub_gh(_make_gh_dispatcher(runs_json=runs))

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.runs[0].conclusion == "success"


def test_collect_github_ok_parses_pr_count(stub_gh, tmp_path):
    prs = json.dumps(
        [
            {
                "number": 7,
                "title": "A",
                "author": {"login": "octocat"},
                "url": "https://x/pr/7",
            },
            {
                "number": 8,
                "title": "B",
                "author": {"login": "hubot"},
                "url": "https://x/pr/8",
            },
        ]
    )
    stub_gh(_make_gh_dispatcher(prs_json=prs))

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert len(section.pull_requests) == 2


def test_collect_github_ok_parses_pr_author_login(stub_gh, tmp_path):
    prs = json.dumps(
        [
            {
                "number": 7,
                "title": "A",
                "author": {"login": "octocat"},
                "url": "https://x/pr/7",
            }
        ]
    )
    stub_gh(_make_gh_dispatcher(prs_json=prs))

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.pull_requests[0].author == "octocat"


def test_collect_github_empty_runs_returns_empty_list(stub_gh, tmp_path):
    stub_gh(_make_gh_dispatcher(runs_json="[]"))

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.runs == []


def test_collect_github_empty_runs_is_ok(stub_gh, tmp_path):
    stub_gh(_make_gh_dispatcher(runs_json="[]"))

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.state == AvailabilityState.OK


def test_collect_github_prefers_origin_over_other_github_remote(stub_gh, tmp_path):
    stub_gh(_make_gh_dispatcher())
    remotes = [_github_remote(name="upstream"), _github_remote(name="origin")]

    section = collect_github(tmp_path, "main", remotes)

    assert section.remote_used == "origin"


def test_collect_github_timeout_returns_timeout_state(stub_gh, tmp_path):
    def raising_run_gh(args, stdin=None):
        if args[:2] in (["run", "list"], ["pr", "list"]):
            raise subprocess.TimeoutExpired(cmd="gh", timeout=15)
        return 0, ""

    stub_gh(raising_run_gh)

    section = collect_github(tmp_path, "main", [_github_remote()])

    assert section.state == AvailabilityState.TIMEOUT
