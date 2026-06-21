"""Unit tests for the dashboard Supabase collector (US3).

Stubs the collector's seams so no real `supabase`/network I/O is invoked. Covers
cabal.dashboard_supabase_service.collect_supabase across link/CLI/token paths.
"""

from __future__ import annotations

import subprocess

from cabal import dashboard_supabase_service
from cabal.dashboard_supabase_service import collect_supabase
from cabal.models.dashboard import AvailabilityState

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
