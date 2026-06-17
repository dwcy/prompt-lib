"""Unit tests for the dashboard Vercel collector (US4).

Stubs the collector's seams so no real `vercel`/network I/O is invoked. Covers
cabal.dashboard_vercel_service.collect_vercel across link/CLI/token paths.
"""

from __future__ import annotations

import subprocess

from cabal import dashboard_vercel_service
from cabal.dashboard_vercel_service import collect_vercel
from cabal.models.dashboard import AvailabilityState

_VERCEL_PROJECT_ID = "proj_1"
_VERCEL_ORG_ID = "team_xyz"
_VERCEL_TOKEN = "vrc_unit_test_token_67890"


def _stub_no_vercel_link(monkeypatch) -> None:
    monkeypatch.setattr(
        dashboard_vercel_service, "find_vercel_link", lambda _project: (None, None)
    )


def _stub_vercel_link(
    monkeypatch,
    project_id: str = _VERCEL_PROJECT_ID,
    org_id: str = _VERCEL_ORG_ID,
) -> None:
    monkeypatch.setattr(
        dashboard_vercel_service,
        "find_vercel_link",
        lambda _project: (project_id, org_id),
    )


def _stub_vercel_cli(monkeypatch, present: bool, output: str = "") -> None:
    monkeypatch.setattr(
        dashboard_vercel_service.shutil,
        "which",
        lambda _name: "/usr/bin/vercel" if present else None,
    )

    def fake_run(_args, **_kwargs):
        return subprocess.CompletedProcess(_args, 0, stdout=output, stderr="")

    monkeypatch.setattr(dashboard_vercel_service.subprocess, "run", fake_run)


def _make_vercel_api_dispatcher(handlers: dict[str, tuple[int, object]]):
    def fake_api_get(path, _token):
        for key in sorted(handlers, key=len, reverse=True):
            if key in path:
                return handlers[key]
        return 200, None

    return fake_api_get


def _vercel_enriched_handlers():
    project = {
        "name": "my-app",
        "latestDeployments": [{"readyState": "READY", "url": "my-app.vercel.app"}],
    }
    team = {"slug": "acme", "billing": {"plan": "pro"}}
    members = [{"name": "octocat", "role": "OWNER"}]
    return {
        f"/v9/projects/{_VERCEL_PROJECT_ID}": (200, project),
        f"/v2/teams/{_VERCEL_ORG_ID}/members": (200, members),
        f"/v2/teams/{_VERCEL_ORG_ID}": (200, team),
    }


def test_collect_vercel_not_linked_returns_not_linked(monkeypatch, tmp_path):
    _stub_no_vercel_link(monkeypatch)

    section = collect_vercel(tmp_path)

    assert section.state == AvailabilityState.NOT_LINKED


def test_collect_vercel_baseline_no_token_is_ok(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    _stub_vercel_cli(monkeypatch, present=False)

    section = collect_vercel(tmp_path)

    assert section.state == AvailabilityState.OK


def test_collect_vercel_baseline_no_token_reports_project_id(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    _stub_vercel_cli(monkeypatch, present=False)

    section = collect_vercel(tmp_path)

    assert section.project_id == _VERCEL_PROJECT_ID


def test_collect_vercel_baseline_no_token_enrich_state_token_missing(
    monkeypatch, tmp_path
):
    _stub_vercel_link(monkeypatch)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    _stub_vercel_cli(monkeypatch, present=False)

    section = collect_vercel(tmp_path)

    assert section.enrich_state == AvailabilityState.TOKEN_MISSING


def test_collect_vercel_baseline_no_token_sets_enrich_hint(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    _stub_vercel_cli(monkeypatch, present=False)

    section = collect_vercel(tmp_path)

    assert section.enrich_hint is not None


def test_collect_vercel_baseline_no_token_leaves_project_name_none(
    monkeypatch, tmp_path
):
    _stub_vercel_link(monkeypatch)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    _stub_vercel_cli(monkeypatch, present=False)

    section = collect_vercel(tmp_path)

    assert section.project_name is None


def test_collect_vercel_baseline_no_token_leaves_deployment_status_none(
    monkeypatch, tmp_path
):
    _stub_vercel_link(monkeypatch)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    _stub_vercel_cli(monkeypatch, present=False)

    section = collect_vercel(tmp_path)

    assert section.latest_deployment_status is None


def test_collect_vercel_baseline_no_token_leaves_team_plan_none(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    _stub_vercel_cli(monkeypatch, present=False)

    section = collect_vercel(tmp_path)

    assert section.team_plan is None


def test_collect_vercel_baseline_no_token_leaves_members_empty(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    _stub_vercel_cli(monkeypatch, present=False)

    section = collect_vercel(tmp_path)

    assert section.members == []


def test_collect_vercel_enriched_enrich_state_ok(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.setenv("VERCEL_TOKEN", _VERCEL_TOKEN)
    _stub_vercel_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_vercel_service,
        "_api_get",
        _make_vercel_api_dispatcher(_vercel_enriched_handlers()),
    )

    section = collect_vercel(tmp_path)

    assert section.enrich_state == AvailabilityState.OK


def test_collect_vercel_enriched_populates_project_name(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.setenv("VERCEL_TOKEN", _VERCEL_TOKEN)
    _stub_vercel_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_vercel_service,
        "_api_get",
        _make_vercel_api_dispatcher(_vercel_enriched_handlers()),
    )

    section = collect_vercel(tmp_path)

    assert section.project_name == "my-app"


def test_collect_vercel_enriched_populates_deployment_status(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.setenv("VERCEL_TOKEN", _VERCEL_TOKEN)
    _stub_vercel_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_vercel_service,
        "_api_get",
        _make_vercel_api_dispatcher(_vercel_enriched_handlers()),
    )

    section = collect_vercel(tmp_path)

    assert section.latest_deployment_status == "READY"


def test_collect_vercel_enriched_populates_team_plan(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.setenv("VERCEL_TOKEN", _VERCEL_TOKEN)
    _stub_vercel_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_vercel_service,
        "_api_get",
        _make_vercel_api_dispatcher(_vercel_enriched_handlers()),
    )

    section = collect_vercel(tmp_path)

    assert section.team_plan == "pro"


def test_collect_vercel_enriched_populates_members(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.setenv("VERCEL_TOKEN", _VERCEL_TOKEN)
    _stub_vercel_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_vercel_service,
        "_api_get",
        _make_vercel_api_dispatcher(_vercel_enriched_handlers()),
    )

    section = collect_vercel(tmp_path)

    assert section.members[0].name == "octocat"


def test_collect_vercel_enriched_never_leaks_token_on_section(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.setenv("VERCEL_TOKEN", _VERCEL_TOKEN)
    _stub_vercel_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_vercel_service,
        "_api_get",
        _make_vercel_api_dispatcher(_vercel_enriched_handlers()),
    )

    section = collect_vercel(tmp_path)

    assert _VERCEL_TOKEN not in repr(section)


def test_collect_vercel_token_rejected_sets_enrich_state(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.setenv("VERCEL_TOKEN", _VERCEL_TOKEN)
    _stub_vercel_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_vercel_service, "_api_get", lambda _path, _token: (401, None)
    )

    section = collect_vercel(tmp_path)

    assert section.enrich_state == AvailabilityState.TOKEN_REJECTED


def test_collect_vercel_token_rejected_keeps_baseline_project_id(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.setenv("VERCEL_TOKEN", _VERCEL_TOKEN)
    _stub_vercel_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_vercel_service, "_api_get", lambda _path, _token: (401, None)
    )

    section = collect_vercel(tmp_path)

    assert section.project_id == _VERCEL_PROJECT_ID


def test_collect_vercel_enrich_timeout_sets_timeout_state(monkeypatch, tmp_path):
    _stub_vercel_link(monkeypatch)
    monkeypatch.setenv("VERCEL_TOKEN", _VERCEL_TOKEN)
    _stub_vercel_cli(monkeypatch, present=False)
    monkeypatch.setattr(
        dashboard_vercel_service, "_api_get", lambda _path, _token: (0, None)
    )

    section = collect_vercel(tmp_path)

    assert section.enrich_state == AvailabilityState.TIMEOUT
