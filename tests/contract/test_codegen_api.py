# > 500 LoC justified: one Constitution Gate 3 contract-test suite pinning every clause of
# contracts/codegen-api.md (T016) in one reviewable pass; splitting would fragment a single
# contract's test-first evidence across files a reviewer must then cross-reference by hand.
# -*- coding: utf-8 -*-
"""Contract tests (T016) for specs/021-codegen-eval-modules/contracts/codegen-api.md.

Every codegen read/action surface (`routers/codegen.py`, `actions_catalog/codegen.py`) is a thin
layer over Group A artifacts the `cabal.dotnetgen` subsystem already owns (data-model.md): the
run-record ledger (`ledger.py`), the pending-intent gate (`intent.py`), and stage bindings
(`providers/config.py`). This file drives that layer with REAL files built from those subsystems'
own real dataclasses -- never a mocked filesystem -- so a passing test proves the webapi surface
reads exactly what the CLI would also read (FR-045).

Every read route and every action currently raises `NotWiredError` (404 `not_wired`, T017-T021),
so every test below is expected to FAIL today at its first behavioural assertion -- never at
import/collection time, never on a fixture typo. That is Constitution Gate 3: the test pins the
real contract now, and turns green only once its owning task lands.

Two gaps discovered against the *current* 018 ledger, noted rather than routed around:
  - `StageCost.to_dict()` (ledger.py) never serialises `priced` or a cache-reported marker, so a
    stage entry cannot today distinguish "priced false" from "a real zero" on disk. This suite's
    run-record fixtures add `priced` (bool) and omit `cached_input_tokens` for stages that did not
    report caching -- the natural per-key-presence extension T017 must honour, matching
    `StageCost`'s own Python-side default (`priced: bool = True`) and `Usage.cache_reported`.
  - No spec artifact pins an exact JSON key for "how many pairwise-comparison pairs were excluded
    and why" (FR-039 on the evals side is analogous; this file is codegen-only and does not need
    it). Nothing here invents such a key.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal.dotnetgen import intent as dotnetgen_intent
from cabal.dotnetgen.pipeline import ChangeIntent
from cabal.dotnetgen.providers.config import MODEL_STAGES

from .webapi_fixtures import (
    app_factory,
    auth_headers,
    build_client,
    register_fixture_actions,
)

__all__ = ["app_factory"]

_CANONICAL_STAGES = (*MODEL_STAGES, "verify")  # route, architect, write, verify (schema order)
_FOUR_OUTCOMES = ("completed", "rejected_at_gate", "halted_at_ceiling", "aborted_environment")


# --------------------------------------------------------------------------- fixtures/helpers ---


def _dotnet_project(tmp_path: Path, *, with_csproj: bool = True) -> Path:
    project = tmp_path / "solution"
    project.mkdir()
    if with_csproj:
        (project / "Solution.csproj").write_text(
            "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>", encoding="utf-8"
        )
    (project / "Program.cs").write_text("public class Program {}\n", encoding="utf-8")
    return project


def _write_run_record(project: Path, run_id: str, payload: dict) -> Path:
    runs_dir = project / ".dotnetgen" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{run_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _minimal_run_payload(run_id: str, *, outcome: str = "completed", stage_costs: dict | None = None) -> dict:
    return {
        "run_id": run_id,
        "outcome": outcome,
        "stage_costs": stage_costs if stage_costs is not None else {},
        "retry_budget": {"ceiling": 3, "consumed": 0},
        "wall_clock_seconds": 12.0,
    }


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _propose_real_intent(project: Path, *, request: str = "Add a webhook receiver endpoint"):
    intent = ChangeIntent(
        summary="Add a webhook receiver endpoint",
        target_files=("src/Api/Webhooks/ReceiverEndpoint.cs",),
        target_symbols=("ReceiverEndpoint",),
        rationale="Requested by the developer",
    )
    return dotnetgen_intent.propose(project, request, intent)


def _write_bindings_toml(project: Path, *, route_base_url: str, architect_base_url: str) -> Path:
    path = project / ".dotnetgen" / "bindings.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
[stages.route]
provider = "openai_compatible"
model = "qwen2.5-coder:7b"
base_url = "{route_base_url}"

[stages.architect]
provider = "openai_compatible"
model = "gpt-4.1"
base_url = "{architect_base_url}"

[stages.write]
provider = "openai_compatible"
model = "qwen2.5-coder:7b"
base_url = "{route_base_url}"
""",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------------- availability ---


@pytest.mark.parametrize(
    ("build_project", "expected_reason"),
    [
        (lambda tmp_path: None, "no_project_selected"),
        (lambda tmp_path: _dotnet_project(tmp_path, with_csproj=False), "not_a_dotnet_project"),
    ],
    ids=["no_project_selected", "not_a_dotnet_project"],
)
def test_availability_reports_distinct_reasons_and_never_500s(
    app_factory, tmp_path, build_project, expected_reason
) -> None:
    """FR-002: unavailability is data, never a 500 -- and the two setup-state reasons must stay
    distinguishable from each other (never collapsed into one generic 'unavailable')."""
    project = build_project(tmp_path)
    app, client = build_client(app_factory, project=project)

    response = client.get("/api/codegen/availability", headers=auth_headers())

    assert response.status_code != 500, response.text
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["available"] is False
    assert data["reason"] == expected_reason


# ---------------------------------------------------------------------------------- runs listing ---


def test_runs_listing_marks_malformed_record_readable_false_without_failing_listing(
    app_factory, tmp_path
) -> None:
    """data-model A1: a run directory can be observed mid-write; one bad record must not take the
    whole history list down, and the newest good run must never be paginated away."""
    project = _dotnet_project(tmp_path)
    _write_run_record(project, "20260101T000000Z", _minimal_run_payload("20260101T000000Z"))
    malformed_path = project / ".dotnetgen" / "runs" / "20260201T000000Z.json"
    malformed_path.write_text("{not valid json", encoding="utf-8")

    app, client = build_client(app_factory, project=project)
    response = client.get("/api/codegen/runs", headers=auth_headers())

    assert response.status_code == 200, response.text
    runs = response.json()["data"]["runs"]
    assert len(runs) == 2, "one malformed record must not remove the other run from the listing"
    by_readability = {entry.get("readable", True): entry for entry in runs}
    assert False in by_readability, "the malformed record must be marked readable: false"
    assert by_readability[False].get("error"), "an unreadable entry must carry an error string"
    good = [entry for entry in runs if entry.get("run_id") == "20260101T000000Z"]
    assert good and good[0].get("readable", True) is not False


# ------------------------------------------------------------------------------------ run detail ---


def test_run_detail_lists_every_canonical_stage_including_ones_that_never_ran(
    app_factory, tmp_path
) -> None:
    """FR-018: `route` and `verify` never ran in this run, but must still appear with explicit
    zeros -- a stage silently omitted looks identical to a stage that cost nothing, and those are
    different facts."""
    project = _dotnet_project(tmp_path)
    run_id = "20260301T000000Z"
    payload = _minimal_run_payload(
        run_id,
        stage_costs={
            "architect": {
                "provider": "cli_shell",
                "model": "claude-opus-5",
                "input_tokens": 500,
                "cached_input_tokens": 100,
                "output_tokens": 200,
                "cost_usd": 0.05,
                "wall_clock_seconds": 4.0,
            },
            "write": {
                "provider": "openai_compatible",
                "model": "qwen2.5-coder:7b",
                "input_tokens": 800,
                "output_tokens": 300,
                "cost_usd": 0.0,
                "wall_clock_seconds": 2.0,
                "priced": True,
            },
        },
    )
    _write_run_record(project, run_id, payload)

    app, client = build_client(app_factory, project=project)
    response = client.get(f"/api/codegen/runs/{run_id}", headers=auth_headers())

    assert response.status_code == 200, response.text
    stage_costs = response.json()["data"]["stage_costs"]
    assert set(stage_costs) == set(_CANONICAL_STAGES), (
        "every pipeline stage must be present, including route/verify which never ran"
    )
    for absent_stage in ("route", "verify"):
        stage = stage_costs[absent_stage]
        assert stage.get("cost_usd") == 0.0
        assert stage.get("wall_clock_seconds", 0.0) == 0.0
        usage = stage.get("usage", stage)
        assert usage.get("input_tokens", 0) == 0
        assert usage.get("output_tokens", 0) == 0


def test_run_detail_never_fabricates_a_priced_flag_the_record_cannot_carry(
    app_factory, tmp_path
) -> None:
    """FR-008 as far as the artifact actually permits.

    `ledger.StageCost` carries `priced` in memory, but `to_dict()` never serialises it and
    `run-record.schema.json` sets `additionalProperties: false` -- so a real run record CANNOT
    distinguish a locally-hosted model's genuine zero from an unlisted model's unknown price.
    Both land on disk as `cost_usd: 0`.

    The honest contract is therefore the negative one: the read path must report the distinction
    as UNKNOWN rather than inventing it. Reporting `priced: true` off the back of a bare zero
    would manufacture a measured-free claim the run never made -- exactly the conflation
    ledger.py's docstring says it exists to prevent. Recorded as a finding against 018
    (research.md); when that schema gains `priced`, the sibling test below pins the read path.
    """
    project = _dotnet_project(tmp_path)
    run_id = "20260302T000000Z"
    payload = _minimal_run_payload(
        run_id,
        stage_costs={
            "architect": {
                "provider": "cli_shell",
                "model": "some-unlisted-frontier-model",
                "cost_usd": 0.0,
            },
            "write": {
                "provider": "openai_compatible",
                "model": "qwen2.5-coder:7b",
                "cost_usd": 0.0,
            },
        },
    )
    _write_run_record(project, run_id, payload)

    app, client = build_client(app_factory, project=project)
    response = client.get(f"/api/codegen/runs/{run_id}", headers=auth_headers())

    assert response.status_code == 200, response.text
    stage_costs = response.json()["data"]["stage_costs"]
    for stage in ("architect", "write"):
        assert stage_costs[stage]["cost_usd"] == 0.0
        assert stage_costs[stage].get("priced") is None, (
            f"{stage}: the record carries no `priced` key, so the API must report unknown "
            "(null) -- never true, which would assert a measured-free run that never happened"
        )


def test_run_detail_preserves_a_priced_flag_once_the_record_carries_one(
    app_factory, tmp_path
) -> None:
    """Forward-compatibility for the finding above: if 018's schema gains `priced`, the read
    path must pass it through untouched rather than re-deriving it from a zero cost."""
    project = _dotnet_project(tmp_path)
    run_id = "20260303T000000Z"
    payload = _minimal_run_payload(
        run_id,
        stage_costs={
            "architect": {
                "provider": "cli_shell",
                "model": "some-unlisted-frontier-model",
                "cost_usd": 0.0,
                "priced": False,
            },
            "write": {
                "provider": "openai_compatible",
                "model": "qwen2.5-coder:7b",
                "cost_usd": 0.0,
                "priced": True,
            },
        },
    )
    _write_run_record(project, run_id, payload)

    app, client = build_client(app_factory, project=project)
    response = client.get(f"/api/codegen/runs/{run_id}", headers=auth_headers())

    assert response.status_code == 200, response.text
    stage_costs = response.json()["data"]["stage_costs"]
    assert stage_costs["architect"]["priced"] is False, (
        "an unlisted model's zero must read as unknown, not as a measured free run"
    )
    assert stage_costs["write"]["priced"] is True, "a local model's zero is a real, known zero"


def test_run_detail_cache_figures_absent_not_zero_when_provider_never_reported_them(
    app_factory, tmp_path
) -> None:
    """data-model A2: 'Usage.cache_reported is false for providers that cannot say; rendering a
    zero there would fabricate data (FR-008)'. A stage whose raw record never carried a cache
    count must not gain one on the way out, while a stage that did report caching must keep it."""
    project = _dotnet_project(tmp_path)
    run_id = "20260303T000000Z"
    payload = _minimal_run_payload(
        run_id,
        stage_costs={
            "architect": {
                # No cached_input_tokens key at all: this provider never reports caching.
                "provider": "cli_shell",
                "model": "claude-opus-5",
                "input_tokens": 500,
                "output_tokens": 200,
                "cost_usd": 0.05,
            },
            "write": {
                "provider": "openai_compatible",
                "model": "qwen2.5-coder:7b",
                "input_tokens": 800,
                "cached_input_tokens": 640,
                "output_tokens": 300,
                "cost_usd": 0.0,
            },
        },
    )
    _write_run_record(project, run_id, payload)

    app, client = build_client(app_factory, project=project)
    response = client.get(f"/api/codegen/runs/{run_id}", headers=auth_headers())

    assert response.status_code == 200, response.text
    stage_costs = response.json()["data"]["stage_costs"]
    architect_usage = stage_costs["architect"].get("usage", stage_costs["architect"])
    assert "cached_input_tokens" not in architect_usage, (
        "a provider that never reported caching must not gain a fabricated cache figure"
    )
    write_usage = stage_costs["write"].get("usage", stage_costs["write"])
    assert write_usage.get("cached_input_tokens") == 640


def test_run_detail_repair_spend_is_reported_separately_from_initial_spend(
    app_factory, tmp_path
) -> None:
    """FR-019: 'a pipeline that looks cheap per call but repairs three times is not cheap' --
    the two figures must never be summed into one, un-attributable total."""
    project = _dotnet_project(tmp_path)
    run_id = "20260304T000000Z"
    payload = _minimal_run_payload(run_id)
    payload["derived"] = {
        "edit_success_rate": 1.0,
        "first_attempt_build_green": False,
        "initial_attempt_cost_usd": 0.05,
        "repair_cost_usd": 0.12,
        "reconciled": True,
    }
    _write_run_record(project, run_id, payload)

    app, client = build_client(app_factory, project=project)
    response = client.get(f"/api/codegen/runs/{run_id}", headers=auth_headers())

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    derived = data.get("derived", data)
    assert derived["initial_attempt_cost_usd"] == 0.05
    assert derived["repair_cost_usd"] == 0.12
    assert derived["initial_attempt_cost_usd"] != derived["repair_cost_usd"] + derived["initial_attempt_cost_usd"]


@pytest.mark.parametrize("outcome", _FOUR_OUTCOMES)
def test_run_detail_outcome_is_one_of_exactly_four_values_never_collapsed(
    app_factory, tmp_path, outcome
) -> None:
    """data-model A3 (authoritative over this contract doc's stray 'six values' line, which
    contradicts both data-model.md and contracts/run-record.schema.json's closed four-value enum):
    `aborted_environment` and `halted_at_ceiling` must read back exactly as recorded, never
    remapped to a generic 'failed'/'error' string (FR-016, FR-017)."""
    project = _dotnet_project(tmp_path)
    run_id = f"20260305T00000{_FOUR_OUTCOMES.index(outcome)}Z"
    _write_run_record(project, run_id, _minimal_run_payload(run_id, outcome=outcome))

    app, client = build_client(app_factory, project=project)
    response = client.get(f"/api/codegen/runs/{run_id}", headers=auth_headers())

    assert response.status_code == 200, response.text
    assert response.json()["data"]["outcome"] == outcome


# ------------------------------------------------------------------------------ pending intent ---


def test_pending_intent_stale_flag_is_computed_at_read_time_not_cached(app_factory, tmp_path) -> None:
    """research.md R3: `stale` must reflect the CURRENT solution fingerprint on every read, never
    a value frozen at propose-time -- proven by mutating the tree between two reads of the same
    pending intent with no new proposal in between."""
    project = _dotnet_project(tmp_path)
    _propose_real_intent(project)

    app, client = build_client(app_factory, project=project)
    first = client.get("/api/codegen/pending", headers=auth_headers())
    assert first.status_code == 200, first.text
    assert first.json()["data"]["stale"] is False

    (project / "Program.cs").write_text(
        "public class Program { public static void Main() {} }\n", encoding="utf-8"
    )

    second = client.get("/api/codegen/pending", headers=auth_headers())
    assert second.status_code == 200, second.text
    assert second.json()["data"]["stale"] is True, (
        "the solution changed after propose; a cached stale flag would still read false here"
    )


def test_pending_intent_has_no_expiry_even_when_very_old(app_factory, tmp_path) -> None:
    """research.md R3: 'A pending intent survives backend restarts because it is a file' and
    carries no TTL -- an ancient `created_at` must not make the gate disappear or expire."""
    project = _dotnet_project(tmp_path)
    pending = _propose_real_intent(project)
    stale_payload = pending.to_dict()
    stale_payload["created_at"] = "2000-01-01T00:00:00+00:00"
    dotnetgen_intent.pending_path(project).write_text(
        json.dumps(stale_payload, indent=2), encoding="utf-8"
    )

    app, client = build_client(app_factory, project=project)
    response = client.get("/api/codegen/pending", headers=auth_headers())

    assert response.status_code == 200, response.text
    assert response.json()["data"] is not None, "a decades-old pending intent must not be treated as expired"
    assert response.json()["data"]["token"] == pending.token


# ------------------------------------------------------------------------------------- bindings ---


def test_bindings_is_local_read_from_provider_instance_not_provider_name(app_factory, tmp_path) -> None:
    """data-model B2: 'is_local must be asked of the provider instance, never inferred from its
    name' -- `openai_compatible` serves both a local Ollama endpoint and hosted OpenAI, so two
    stages sharing that one provider name must still disagree on is_local."""
    project = _dotnet_project(tmp_path)
    _write_bindings_toml(
        project,
        route_base_url="http://localhost:11434/v1",
        architect_base_url="https://api.openai.com/v1",
    )

    app, client = build_client(app_factory, project=project)
    response = client.get("/api/codegen/bindings", headers=auth_headers())

    assert response.status_code == 200, response.text
    bindings = {b["stage"]: b for b in response.json()["data"]["bindings"]}
    assert bindings["route"]["provider"] == bindings["architect"]["provider"] == "openai_compatible"
    assert bindings["route"]["is_local"] is True
    assert bindings["architect"]["is_local"] is False, (
        "a name-based guess would report this hosted OpenAI binding as free"
    )


# --------------------------------------------------------------------------------------- plan ---


def test_codegen_plan_writes_nothing_to_the_target_project(app_factory, tmp_path) -> None:
    """FR-014/SC-003, the load-bearing safety test: the working tree must be byte-identical
    before and after a `codegen.plan` run that reaches the approval gate. Prepare/execute is
    driven exactly as a real caller would; today it fails at the very first assertion because
    prepare() is a `NotWiredError` stub (T018), never because this test skipped the real check."""
    project = _dotnet_project(tmp_path)
    before = _snapshot_tree(project)

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    prepared = client.post(
        "/api/actions/codegen.plan/prepare",
        json={"request": "Add a webhook receiver endpoint"},
        headers=auth_headers(),
    )
    assert prepared.status_code == 200, prepared.text
    ticket = prepared.json()["data"]

    executed = client.post(
        "/api/actions/codegen.plan/execute",
        json={"ticket_id": ticket["ticket_id"]},
        headers=auth_headers(),
    )
    assert executed.status_code == 202, executed.text
    job_id = executed.json()["data"]["job_id"]
    _wait_for_job_terminal(client, job_id)

    after = _snapshot_tree(project)
    assert after == before, "codegen.plan must never write to the target project (FR-014)"


def _wait_for_job_terminal(client, job_id: str, timeout: float = 10.0) -> dict:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = client.get(f"/api/jobs/{job_id}", headers=auth_headers()).json()["data"]
        if record["state"] in {"succeeded", "failed", "cancelled"}:
            return record
        time.sleep(0.05)
    pytest.fail(f"job {job_id} never reached a terminal state within {timeout}s")


# ------------------------------------------------------------------------------------- approve ---


def test_codegen_approve_digest_binds_to_pending_intent_token_and_refuses_stale_fingerprint(
    app_factory, tmp_path
) -> None:
    """data-model B4: the precondition digest binds to the pending intent's own token so 'the
    webapi ticket and the subsystem's own gate cannot disagree by construction'. Refusing a
    fingerprint that moved between prepare and execute is `409 intent_stale`, an error -- never
    an automatic re-prompt (contract)."""
    project = _dotnet_project(tmp_path)
    pending = _propose_real_intent(project)

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    prepared = client.post(
        "/api/actions/codegen.approve/prepare",
        json={"token": pending.token},
        headers=auth_headers(),
    )
    assert prepared.status_code == 200, prepared.text
    ticket = prepared.json()["data"]
    assert ticket["precondition_digest"], "digest must be bound to the pending intent's token"

    # The solution moves between prepare and execute -- the fingerprint the token was derived
    # against no longer matches.
    (project / "Program.cs").write_text(
        "public class Program { /* hand-edited after approval was prepared */ }\n", encoding="utf-8"
    )

    executed = client.post(
        "/api/actions/codegen.approve/execute",
        json={"ticket_id": ticket["ticket_id"]},
        headers=auth_headers(),
    )
    assert executed.status_code == 409, executed.text
    assert executed.json()["error"]["code"] == "intent_stale"


def test_codegen_approve_execute_on_an_already_redeemed_token_is_refused(app_factory, tmp_path) -> None:
    """contract: 'A token already redeemed is refused - approval is not replayable.'"""
    project = _dotnet_project(tmp_path)
    _write_bindings_toml(
        project,
        route_base_url="http://localhost:1/unreachable",
        architect_base_url="http://localhost:1/unreachable",
    )
    pending = _propose_real_intent(project)

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    first_prepare = client.post(
        "/api/actions/codegen.approve/prepare",
        json={"token": pending.token},
        headers=auth_headers(),
    )
    assert first_prepare.status_code == 200, first_prepare.text
    first_ticket = first_prepare.json()["data"]
    first_execute = client.post(
        "/api/actions/codegen.approve/execute",
        json={"ticket_id": first_ticket["ticket_id"]},
        headers=auth_headers(),
    )
    assert first_execute.status_code == 202, first_execute.text
    _wait_for_job_terminal(client, first_execute.json()["data"]["job_id"])

    second_prepare = client.post(
        "/api/actions/codegen.approve/prepare",
        json={"token": pending.token},
        headers=auth_headers(),
    )
    assert second_prepare.status_code in {200, 404, 409}, second_prepare.text
    if second_prepare.status_code == 200:
        second_ticket = second_prepare.json()["data"]
        second_execute = client.post(
            "/api/actions/codegen.approve/execute",
            json={"ticket_id": second_ticket["ticket_id"]},
            headers=auth_headers(),
        )
        assert second_execute.status_code in {404, 409}, (
            "a redeemed token must be refused, not replayed"
        )


def test_codegen_approve_failed_apply_leaves_pending_intent_intact(app_factory, tmp_path) -> None:
    """A failed apply must leave the pending intent intact so the developer can retry without
    re-approving. An unreachable provider binding forces a real, deterministic apply failure --
    no mocking of the pipeline itself."""
    project = _dotnet_project(tmp_path)
    _write_bindings_toml(
        project,
        route_base_url="http://localhost:1/unreachable",
        architect_base_url="http://localhost:1/unreachable",
    )
    pending = _propose_real_intent(project)

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    prepared = client.post(
        "/api/actions/codegen.approve/prepare",
        json={"token": pending.token},
        headers=auth_headers(),
    )
    assert prepared.status_code == 200, prepared.text
    ticket = prepared.json()["data"]
    executed = client.post(
        "/api/actions/codegen.approve/execute",
        json={"ticket_id": ticket["ticket_id"]},
        headers=auth_headers(),
    )
    assert executed.status_code == 202, executed.text
    record = _wait_for_job_terminal(client, executed.json()["data"]["job_id"])
    assert record["state"] == "failed", "an unreachable provider must fail the apply, not succeed"

    still_pending = dotnetgen_intent.load_pending(project)
    assert still_pending.token == pending.token, "a failed apply must not clear the approval gate"


def test_codegen_approve_effect_preview_files_changed_mirrors_the_intent_plan(app_factory, tmp_path) -> None:
    """contract: \"prepare's effect_preview populates files_changed from the intent's file list, so
    the confirmation the user sees is the plan itself\" -- no second, independently-built preview."""
    project = _dotnet_project(tmp_path)
    pending = _propose_real_intent(project)

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    prepared = client.post(
        "/api/actions/codegen.approve/prepare",
        json={"token": pending.token},
        headers=auth_headers(),
    )
    assert prepared.status_code == 200, prepared.text
    files_changed = prepared.json()["data"]["effect_preview"]["files_changed"]
    assert list(files_changed) == list(pending.intent.target_files)


# -------------------------------------------------------------------------------------- reject ---


def test_codegen_reject_clears_intent_leaves_tree_unmodified_and_audits_the_decision(
    app_factory, tmp_path
) -> None:
    """contract: reject clears the pending intent, records outcome `rejected_at_gate`, leaves the
    tree unmodified, and writes an audit entry -- 'a rejection is a decision worth keeping'
    (FR-006, data-model B5)."""
    project = _dotnet_project(tmp_path)
    pending = _propose_real_intent(project)
    before = _snapshot_tree(project)
    runs_before = len(list((project / ".dotnetgen" / "runs").glob("*.json"))) if (
        project / ".dotnetgen" / "runs"
    ).is_dir() else 0

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    prepared = client.post(
        "/api/actions/codegen.reject/prepare",
        json={"token": pending.token},
        headers=auth_headers(),
    )
    assert prepared.status_code == 200, prepared.text
    ticket = prepared.json()["data"]
    executed = client.post(
        "/api/actions/codegen.reject/execute",
        json={"ticket_id": ticket["ticket_id"]},
        headers=auth_headers(),
    )
    assert executed.status_code == 200, executed.text

    with pytest.raises(dotnetgen_intent.NoPendingIntentError):
        dotnetgen_intent.load_pending(project)
    assert _snapshot_tree(project) == before, "reject must never modify the working tree"

    audit = client.get("/api/audit", headers=auth_headers())
    matching = [e for e in audit.json()["data"]["entries"] if e["ticket_id"] == ticket["ticket_id"]]
    assert len(matching) == 1, "reject must write exactly one audit entry (FR-006)"

    runs_dir = project / ".dotnetgen" / "runs"
    runs_after = list(runs_dir.glob("*.json")) if runs_dir.is_dir() else []
    outcomes = [json.loads(p.read_text(encoding="utf-8")).get("outcome") for p in runs_after]
    assert len(runs_after) == runs_before + 1, "reject must record a run outcome, per data-model A3"
    assert "rejected_at_gate" in outcomes


# ---------------------------------------------------------------------------------- new_service ---


def test_new_service_destination_escaping_project_is_refused_after_normalisation(
    app_factory, tmp_path
) -> None:
    """FR-011a/research.md R10: 'a relative path containing .. passes a naive prefix test' -- the
    check must run on the normalised, resolved path, not the raw string."""
    project = _dotnet_project(tmp_path)
    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    response = client.post(
        "/api/actions/codegen.new_service/prepare",
        json={
            "template": "minimal-service",
            "destination": "safe/../../outside",
            "description": "A new service",
        },
        headers=auth_headers(),
    )

    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "destination_outside_project"


def test_new_service_non_empty_existing_destination_is_refused_and_never_merged_into(
    app_factory, tmp_path
) -> None:
    """FR-011b: an existing, non-empty destination is refused with `409 destination_not_empty`."""
    project = _dotnet_project(tmp_path)
    destination = project / "src" / "AlreadyThere"
    destination.mkdir(parents=True)
    (destination / "Existing.cs").write_text("public class Existing {}\n", encoding="utf-8")
    before = _snapshot_tree(project)

    app, client = build_client(app_factory, project=project)
    register_fixture_actions(app)

    response = client.post(
        "/api/actions/codegen.new_service/prepare",
        json={
            "template": "minimal-service",
            "destination": "src/AlreadyThere",
            "description": "A new service",
        },
        headers=auth_headers(),
    )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "destination_not_empty"
    assert _snapshot_tree(project) == before, "a refused destination must never be merged into"


# ----------------------------------------------------------------------------------- concurrency ---


def test_exclusive_resource_codegen_refuses_a_second_launch_naming_the_blocking_job(
    app_factory, tmp_path
) -> None:
    """contract: 'A second launch while one is running is refused with 409 naming the blocking
    job.' Exercised against the exact resource name (`\"codegen\"`) codegen's run-starting actions
    are specified to use (data-model B4), via the generic job-emitter fixture action -- the
    mechanism codegen.plan/new_service will hand off to once T018/T021 wire real execute() bodies
    that call `state.jobs.create(..., exclusive_resource=\"codegen\")`."""
    app, client = build_client(app_factory)
    register_fixture_actions(app)

    def _launch():
        prepared = client.post(
            "/api/actions/test.job_emitter/prepare",
            json={"lines": 20, "delay_ms": 50, "exclusive_resource": "codegen"},
            headers=auth_headers(),
        )
        return client.post(
            "/api/actions/test.job_emitter/execute",
            json={"ticket_id": prepared.json()["data"]["ticket_id"]},
            headers=auth_headers(),
        )

    first = _launch()
    assert first.status_code == 202, first.text
    first_job_id = first.json()["data"]["job_id"]

    second = _launch()

    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "job_conflict"
    assert second.json()["error"]["blocking_job_id"] == first_job_id
