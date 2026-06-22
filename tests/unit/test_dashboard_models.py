"""Unit tests for cabal.models.dashboard — section dataclasses + snapshot cache round-trip.

Covers C-M1 (constructible with defaults), C-M2 (token-free JSON-safe to_cacheable),
C-M3 (tolerant from_cached), C-M4 (no Textual/subprocess import side effects).
"""

from __future__ import annotations

import json

import pytest

from cabal.models.dashboard import (
    AvailabilityState,
    DashboardSnapshot,
    GitHubSection,
    GitRemote,
    GitSection,
    ProjectMember,
    PullRequest,
    SupabaseSection,
    VercelSection,
    WorkflowRun,
)


@pytest.mark.parametrize("state", list(AvailabilityState))
def test_git_section_constructs_with_state_only_and_defaults_empty(state):
    section = GitSection(state=state)

    assert section.state == state
    assert section.current_branch is None
    assert section.detached is False
    assert section.local_branches == []
    assert section.remotes == []
    assert section.hint is None


@pytest.mark.parametrize("state", list(AvailabilityState))
def test_github_section_constructs_with_state_only_and_defaults_empty(state):
    section = GitHubSection(state=state)

    assert section.state == state
    assert section.connected is False
    assert section.owner_repo is None
    assert section.remote_used is None
    assert section.runs == []
    assert section.pull_requests == []
    assert section.hint is None


@pytest.mark.parametrize("state", list(AvailabilityState))
def test_supabase_section_constructs_with_state_only_and_defaults_empty(state):
    section = SupabaseSection(state=state)

    assert section.state == state
    assert section.enrich_state == AvailabilityState.TOKEN_MISSING
    assert section.project_ref is None
    assert section.members == []
    assert section.hint is None


@pytest.mark.parametrize("state", list(AvailabilityState))
def test_vercel_section_constructs_with_state_only_and_defaults_empty(state):
    section = VercelSection(state=state)

    assert section.state == state
    assert section.enrich_state == AvailabilityState.TOKEN_MISSING
    assert section.project_name is None
    assert section.members == []
    assert section.hint is None


def _populated_snapshot() -> DashboardSnapshot:
    return DashboardSnapshot(
        project_path="/tmp/proj",
        captured_at="2026-06-15T10:00:00+00:00",
        git=GitSection(
            state=AvailabilityState.OK,
            current_branch="main",
            detached=False,
            local_branches=["main", "dev"],
            remotes=[GitRemote("origin", "https://github.com/o/r", True)],
            hint=None,
        ),
        github=GitHubSection(
            state=AvailabilityState.OK,
            connected=True,
            owner_repo="o/r",
            remote_used="origin",
            runs=[
                WorkflowRun(
                    name="CI",
                    branch="main",
                    status="completed",
                    conclusion="success",
                    url="https://github.com/o/r/actions/runs/1",
                    created_at="2026-06-15T09:00:00+00:00",
                )
            ],
            pull_requests=[
                PullRequest(
                    number=7,
                    title="Add dashboard",
                    author="alice",
                    url="https://github.com/o/r/pull/7",
                )
            ],
            hint=None,
        ),
        supabase=SupabaseSection(
            state=AvailabilityState.OK,
            enrich_state=AvailabilityState.OK,
            project_ref="abcdefgh",
            dashboard_url="https://supabase.com/dashboard/project/abcdefgh",
            schema_visualizer_url="https://supabase.com/dashboard/project/abcdefgh/database/schemas",
            db_location="us-east-1",
            last_migration="0001_init",
            status="ACTIVE_HEALTHY",
            region="us-east-1",
            plan_name="pro",
            last_backup="2026-06-14",
            github_connected=True,
            members=[ProjectMember("alice", "owner")],
            hint=None,
            enrich_hint=None,
        ),
        vercel=VercelSection(
            state=AvailabilityState.OK,
            enrich_state=AvailabilityState.OK,
            project_name="my-app",
            project_id="prj_1",
            dashboard_url="https://vercel.com/o/my-app",
            latest_deployment_url="https://my-app.vercel.app",
            latest_deployment_status="READY",
            team_plan="pro",
            region="iad1",
            members=[ProjectMember("alice", "member")],
            hint=None,
            enrich_hint=None,
        ),
    )


def _flatten_keys(obj) -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.append(key)
            keys.extend(_flatten_keys(value))
    elif isinstance(obj, list):
        for item in obj:
            keys.extend(_flatten_keys(item))
    return keys


def test_to_cacheable_is_json_serialisable():
    snap = _populated_snapshot()

    encoded = json.dumps(snap.to_cacheable())

    assert isinstance(encoded, str)


def test_to_cacheable_has_no_token_or_secret_named_keys():
    snap = _populated_snapshot()

    keys = _flatten_keys(snap.to_cacheable())

    assert not any("token" in k.lower() or "secret" in k.lower() for k in keys)


def test_to_cacheable_coerces_enum_states_to_plain_strings():
    snap = _populated_snapshot()

    cacheable = snap.to_cacheable()

    assert cacheable["git"]["state"] == "ok"


def test_from_cached_returns_none_for_none():
    assert DashboardSnapshot.from_cached(None) is None


def test_from_cached_returns_none_for_bogus_payload():
    assert DashboardSnapshot.from_cached({"bogus": 1}) is None


def test_from_cached_round_trips_key_fields():
    snap = _populated_snapshot()

    restored = DashboardSnapshot.from_cached(snap.to_cacheable())

    assert restored is not None
    assert restored.project_path == snap.project_path
    assert restored.captured_at == snap.captured_at
    assert restored.git == snap.git
    assert restored.github == snap.github
    assert restored.supabase == snap.supabase
    assert restored.vercel == snap.vercel


def test_module_imports_no_textual_or_subprocess_symbols():
    import cabal.models.dashboard as module

    leaked = {
        name
        for name in vars(module)
        if name.lower().startswith(("textual", "subprocess"))
    }

    assert leaked == set()
