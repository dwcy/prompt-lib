"""Unit tests for the dashboard external-service collectors (US2/US3/US4).

Stubs each collector's seams so no real `gh`/network I/O is invoked. US2 covers
cabal.dashboard_github_service.collect_github across remote/CLI/auth/data paths.
US3 and US4 append their own cases below.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from cabal import dashboard_github_service, dashboard_supabase_service
from cabal.dashboard_github_service import collect_github
from cabal.dashboard_supabase_service import collect_supabase
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


# --- US3: collect_supabase --------------------------------------------------

_SUPA_REF = "abcdefgh"
_SUPA_TOKEN = "sbp_unit_test_token_12345"

_MIGRATION_OUTPUT = """\
   LOCAL      | REMOTE     | TIME (UTC)
  ---------- | ---------- | -------------------
   20240101  | 20240101   | 2024-01-01 00:00:00
   20240202  | 20240202   | 2024-02-02 00:00:00
"""


def _stub_no_supabase_ref(monkeypatch) -> None:
    monkeypatch.setattr(
        dashboard_supabase_service, "find_supabase_ref", lambda _project: None
    )


def _stub_supabase_ref(monkeypatch, ref: str = _SUPA_REF) -> None:
    monkeypatch.setattr(
        dashboard_supabase_service, "find_supabase_ref", lambda _project: ref
    )


def _stub_supabase_cli(monkeypatch, present: bool, output: str = "") -> None:
    monkeypatch.setattr(
        dashboard_supabase_service.shutil,
        "which",
        lambda _name: "/usr/bin/supabase" if present else None,
    )

    def fake_run(_args, **_kwargs):
        return subprocess.CompletedProcess(_args, 0, stdout=output, stderr="")

    monkeypatch.setattr(dashboard_supabase_service.subprocess, "run", fake_run)


def _make_api_dispatcher(handlers: dict[str, tuple[int, object]]):
    def fake_api_get(path, _token):
        for key in sorted(handlers, key=len, reverse=True):
            if key in path:
                return handlers[key]
        return 200, []

    return fake_api_get


def test_collect_supabase_not_linked_returns_not_linked(monkeypatch, tmp_path):
    _stub_no_supabase_ref(monkeypatch)

    section = collect_supabase(tmp_path)

    assert section.state == AvailabilityState.NOT_LINKED


def test_collect_supabase_baseline_no_token_is_ok(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert section.state == AvailabilityState.OK


def test_collect_supabase_baseline_no_token_reports_ref(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert section.project_ref == _SUPA_REF


def test_collect_supabase_baseline_no_token_reports_db_location(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert section.db_location == f"db.{_SUPA_REF}.supabase.co"


def test_collect_supabase_baseline_dashboard_url_contains_ref(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert _SUPA_REF in section.dashboard_url


def test_collect_supabase_baseline_schema_url_contains_ref(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert _SUPA_REF in section.schema_visualizer_url


def test_collect_supabase_baseline_parses_last_migration(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert section.last_migration == "20240202"


def test_collect_supabase_no_token_enrich_state_token_missing(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert section.enrich_state == AvailabilityState.TOKEN_MISSING


def test_collect_supabase_no_token_sets_enrich_hint(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert section.enrich_hint is not None


def test_collect_supabase_no_token_leaves_status_none(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert section.status is None


def test_collect_supabase_no_token_leaves_region_none(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert section.region is None


def test_collect_supabase_no_token_leaves_plan_name_none(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert section.plan_name is None


def test_collect_supabase_no_token_leaves_last_backup_none(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert section.last_backup is None


def test_collect_supabase_no_token_leaves_members_empty(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    _stub_supabase_cli(monkeypatch, present=True, output=_MIGRATION_OUTPUT)

    section = collect_supabase(tmp_path)

    assert section.members == []


def test_collect_supabase_no_cli_is_still_ok(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(dashboard_supabase_service.shutil, "which", lambda _name: None)

    section = collect_supabase(tmp_path)

    assert section.state == AvailabilityState.OK


def test_collect_supabase_no_cli_reports_ref(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(dashboard_supabase_service.shutil, "which", lambda _name: None)

    section = collect_supabase(tmp_path)

    assert section.project_ref == _SUPA_REF


def test_collect_supabase_no_cli_reports_db_location(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(dashboard_supabase_service.shutil, "which", lambda _name: None)

    section = collect_supabase(tmp_path)

    assert section.db_location == f"db.{_SUPA_REF}.supabase.co"


def test_collect_supabase_no_cli_last_migration_none(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(dashboard_supabase_service.shutil, "which", lambda _name: None)

    section = collect_supabase(tmp_path)

    assert section.last_migration is None


def _enriched_handlers():
    project = {
        "id": _SUPA_REF,
        "status": "ACTIVE_HEALTHY",
        "region": "us-east-1",
        "organization_id": "org1",
    }
    backup = {"backups": [{"inserted_at": "2026-06-10T00:00:00Z"}]}
    members = [{"username": "octocat", "role_name": "Owner"}]
    return {
        "/v1/projects": (200, [project]),
        "/database/backups": (200, backup),
        "/members": (200, members),
    }


def test_collect_supabase_enriched_enrich_state_ok(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", _SUPA_TOKEN)
    _stub_supabase_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_supabase_service,
        "_api_get",
        _make_api_dispatcher(_enriched_handlers()),
    )

    section = collect_supabase(tmp_path)

    assert section.enrich_state == AvailabilityState.OK


def test_collect_supabase_enriched_populates_status(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", _SUPA_TOKEN)
    _stub_supabase_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_supabase_service,
        "_api_get",
        _make_api_dispatcher(_enriched_handlers()),
    )

    section = collect_supabase(tmp_path)

    assert section.status == "ACTIVE_HEALTHY"


def test_collect_supabase_enriched_populates_region(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", _SUPA_TOKEN)
    _stub_supabase_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_supabase_service,
        "_api_get",
        _make_api_dispatcher(_enriched_handlers()),
    )

    section = collect_supabase(tmp_path)

    assert section.region == "us-east-1"


def test_collect_supabase_enriched_populates_last_backup(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", _SUPA_TOKEN)
    _stub_supabase_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_supabase_service,
        "_api_get",
        _make_api_dispatcher(_enriched_handlers()),
    )

    section = collect_supabase(tmp_path)

    assert section.last_backup == "2026-06-10T00:00:00Z"


def test_collect_supabase_enriched_populates_members(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", _SUPA_TOKEN)
    _stub_supabase_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_supabase_service,
        "_api_get",
        _make_api_dispatcher(_enriched_handlers()),
    )

    section = collect_supabase(tmp_path)

    assert section.members[0].name == "octocat"


def test_collect_supabase_enriched_never_leaks_token_on_section(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", _SUPA_TOKEN)
    _stub_supabase_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_supabase_service,
        "_api_get",
        _make_api_dispatcher(_enriched_handlers()),
    )

    section = collect_supabase(tmp_path)

    assert _SUPA_TOKEN not in repr(section)


def test_collect_supabase_token_rejected_sets_enrich_state(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", _SUPA_TOKEN)
    _stub_supabase_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_supabase_service,
        "_api_get",
        lambda _path, _token: (401, None),
    )

    section = collect_supabase(tmp_path)

    assert section.enrich_state == AvailabilityState.TOKEN_REJECTED


def test_collect_supabase_token_rejected_sets_enrich_hint(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", _SUPA_TOKEN)
    _stub_supabase_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_supabase_service,
        "_api_get",
        lambda _path, _token: (401, None),
    )

    section = collect_supabase(tmp_path)

    assert section.enrich_hint is not None


def test_collect_supabase_token_rejected_keeps_baseline_ref(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", _SUPA_TOKEN)
    _stub_supabase_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_supabase_service,
        "_api_get",
        lambda _path, _token: (401, None),
    )

    section = collect_supabase(tmp_path)

    assert section.project_ref == _SUPA_REF


def test_collect_supabase_enrich_timeout_sets_timeout_state(monkeypatch, tmp_path):
    _stub_supabase_ref(monkeypatch)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", _SUPA_TOKEN)
    _stub_supabase_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_supabase_service,
        "_api_get",
        lambda _path, _token: (0, None),
    )

    section = collect_supabase(tmp_path)

    assert section.enrich_state == AvailabilityState.TIMEOUT
