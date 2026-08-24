# -*- coding: utf-8 -*-
"""Integration test (T036) for the greenfield path: empty directory to a service that serves.

This is the end-to-end assertion behind SC-001. One description, one template choice, one
approval - and the result compiles, passes its tests, and answers a request. Nothing else is
asked of the developer along the way.

## What is real here and what is scripted

Everything the *pipeline* owns runs for real. `dotnet new` runs, the template overlay is copied,
`dotnet build` compiles, `dotnet test` executes, and the edits are applied by the real applier to
files on disk. This module is the only one in the dotnetgen suite that invokes the .NET SDK, and
that is deliberate: T036 asks whether the pipeline produces a *working solution*, and a stubbed
`dotnet.verify` cannot answer that question.

Only the model reply is scripted. What is under test is the pipeline's handling of an approved
intent, not whether a given model happens to emit good C#. A live model here would make the test
billed, slow, and non-deterministic while asserting nothing the scripted batch does not - the same
reasoning as `test_feature_edit.py`, and for the same reason.

## How "serves health" is asserted

It is asserted by the template's own xUnit tests, not by an HTTP client in this file. Each
template ships `HealthEndpointTests`, which drives the real host through
`WebApplicationFactory<Program>` and issues `GET /health`. A green `dotnet test` therefore *is*
the health assertion. Standing up a second client here would test ASP.NET Core rather than this
pipeline, and would duplicate a check the scaffold already carries.

The feature run adds `/version` the same way: its generated test hits the live route, so a green
verify proves the new endpoint is served, not merely that it compiled.

## How "no architecture question after the template choice" is asserted

Structurally, in three places, rather than by inspecting prose:

* the scaffold consults no provider at all - the call counter is still zero after it, which is
  also SC-012's mechanism: the greenfield skeleton costs no tokens;
* the approved run reaches a verified result in a single writing turn, so no second turn asked
  anything back;
* `pipeline.Pipeline` holds no architect field, so a repair cannot reopen the design (FR-020).

## What this test does NOT measure

The live, billed criteria - SC-001's end-to-end wall clock against a hosted model, SC-008, SC-009,
SC-010, SC-011 - are not measured here, because a scripted provider reports no usage and no cost.
The procedure for measuring those by hand, with the exact command per criterion, is in
`specs/018-dotnet-codegen/baseline.md` under "Measuring the remaining exit criteria (T072)".

What this test *does* contribute to SC-001 is the offline half of the budget: the scaffold, build,
edit and verify wall clock, which is the part that does not vary with the model. It is asserted
against the 600-second target and printed so the figure can be read off a run.

## Cost of running it

A cold run pays a NuGet restore and two full builds - expect a couple of minutes. The traversal is
module-scoped so it is paid once for the whole file. Deselect the module with
`pytest -m "not toolchain"`; it skips automatically when `dotnet` is not on PATH.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from cabal.dotnetgen import runner, scaffold, state
from cabal.dotnetgen.edits.relaxation import RELAXATION_EXACT
from cabal.dotnetgen.pipeline import (
    ChangeIntent,
    GateDecision,
    Pipeline,
    RetryBudget,
    RunOutcome,
    RunResult,
)
from cabal.dotnetgen.providers.base import CompletionResult, Usage
from cabal.dotnetgen.templates import registry
from cabal.dotnetgen.verify import dotnet

pytestmark = [
    pytest.mark.toolchain,
    pytest.mark.skipif(
        shutil.which("dotnet") is None,
        reason="the greenfield path is only meaningful against a real .NET SDK",
    ),
]

TEMPLATE_ID = "minimal-service"
"""The smallest template. T036 is about the path, not about template variety - the other two are
covered by the scaffold contract tests, and building all three here would triple the SDK cost for
no additional assertion."""

DESCRIPTION = "A service that reports which version of itself is running."
"""The developer's one sentence. In a live run the architect stage turns this into the intent
below; here the intent is supplied directly, because the gate is what T036 asserts, not the
model's phrasing of what passes through it."""

SC_001_WALL_CLOCK_SECONDS = 600
"""SC-001's target. Asserted against the offline half only - see the module docstring."""

INTENT = ChangeIntent(
    summary=(
        "Add a version slice: a response record, an endpoint that maps GET /version, one line "
        "in Program.cs to register it, and a test that drives the route on the real host."
    ),
    target_files=(
        "src/Api/Features/Version/VersionResponse.cs",
        "src/Api/Features/Version/VersionEndpoint.cs",
        "src/Api/Program.cs",
        "tests/Api.Tests/Features/VersionSlice/VersionEndpointTests.cs",
    ),
    target_symbols=(
        "Api.Features.Version.VersionResponse",
        "Api.Features.Version.VersionEndpoint.MapVersion",
    ),
    rationale="One folder per feature, one Map call per slice, no mediator - the template's shape.",
)

VERSION_RESPONSE_CS = """namespace Api.Features.Version;

/// <summary>The version slice's response body.</summary>
public sealed record VersionResponse(string Version);
"""

VERSION_ENDPOINT_CS = """namespace Api.Features.Version;

/// <summary>Reports the running version. A Query - it returns data and mutates nothing.</summary>
public static class VersionEndpoint
{
    /// <summary>Registers the slice's routes. Every slice exposes exactly one of these.</summary>
    public static IEndpointRouteBuilder MapVersion(this IEndpointRouteBuilder routes)
    {
        routes.MapGet("/version", () => Results.Ok(new VersionResponse("1.0.0")));
        return routes;
    }
}
"""

VERSION_TESTS_CS = """using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;

namespace Api.Tests.Features.VersionSlice;

/// <summary>Drives the real host: a route is only "served" if a request reaches it.</summary>
public sealed class VersionEndpointTests(WebApplicationFactory<Program> factory)
    : IClassFixture<WebApplicationFactory<Program>>
{
    [Fact]
    public async Task Version_returns_ok()
    {
        HttpClient client = factory.CreateClient();

        HttpResponseMessage response = await client.GetAsync("/version");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Contains("1.0.0", await response.Content.ReadAsStringAsync());
    }
}
"""

EDITS = {
    "operations": [
        {
            "file": "src/Api/Features/Version/VersionResponse.cs",
            "anchor_kind": "symbol",
            "symbol": "Api.Features.Version.VersionResponse",
            "disposition": "create-file",
            "content": VERSION_RESPONSE_CS,
            "reason": "the slice's response body",
        },
        {
            "file": "src/Api/Features/Version/VersionEndpoint.cs",
            "anchor_kind": "symbol",
            "symbol": "Api.Features.Version.VersionEndpoint",
            "disposition": "create-file",
            "content": VERSION_ENDPOINT_CS,
            "reason": "maps GET /version",
        },
        {
            "file": "src/Api/Program.cs",
            "anchor_kind": "text",
            "search": "using Api.Features.Health;",
            "disposition": "replace",
            "content": "using Api.Features.Health;\nusing Api.Features.Version;",
            "reason": "the new slice's namespace must be in scope",
        },
        {
            "file": "src/Api/Program.cs",
            "anchor_kind": "text",
            "search": "app.MapHealth();",
            "disposition": "replace",
            "content": "app.MapHealth();\napp.MapVersion();",
            "reason": "one line per feature, per the template contract",
        },
        {
            "file": "tests/Api.Tests/Features/VersionSlice/VersionEndpointTests.cs",
            "anchor_kind": "symbol",
            "symbol": "Api.Tests.Features.VersionSlice.VersionEndpointTests",
            "disposition": "create-file",
            "content": VERSION_TESTS_CS,
            "reason": "prove the route is served, not merely compiled",
        },
    ]
}

OPERATION_COUNT = len(EDITS["operations"])


class ScriptedProvider:
    """Stands in for the writing model and counts how often it was consulted.

    The count is the assertion, not the text: a greenfield run that asked a second question would
    show up here as a second call.
    """

    name = "scripted"

    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)
        self.calls = 0

    def complete(self, request: object) -> CompletionResult:
        self.calls += 1
        reply = self._replies[min(self.calls - 1, len(self._replies) - 1)]
        return CompletionResult(
            text=reply,
            usage=Usage(input_tokens=0, output_tokens=0),
            model="scripted",
            provider=self.name,
        )


_PASSED_COUNT = re.compile(r"Passed:\s*(\d+)")
_EMPTY_FILTER = "No test matches the given testcase filter"


def assert_named_tests_pass(root: Path, name: str, *, expected: int) -> None:
    """Run only the tests whose fully-qualified name contains `name`, and prove they really ran.

    The exit code alone is not enough. `dotnet test` **exits 0 when a filter matches nothing** - it
    prints "No test matches the given testcase filter" and reports success. Asserting only on
    `result.ok` would therefore make a missing endpoint test indistinguishable from a passing one,
    which is exactly the failure mode the cost baseline caught in the unassisted run: a suite that
    could not execute, reported as green (`specs/018-dotnet-codegen/baseline.md`).

    So the passed count is part of the assertion, not decoration.
    """
    result = dotnet.test(root, filter_expression=f"FullyQualifiedName~{name}")

    assert result.ok, result.combined
    assert _EMPTY_FILTER not in result.combined, f"the {name} filter matched no tests at all"

    passed = sum(int(count) for count in _PASSED_COUNT.findall(result.combined))
    assert passed >= expected, (
        f"expected at least {expected} passing test(s) matching {name}, the run reported "
        f"{passed}:\n{result.combined}"
    )


@dataclass
class GreenfieldRun:
    """One traversal of the whole greenfield path, with the timings T036 reports."""

    root: Path
    scaffold_result: scaffold.ScaffoldResult
    provider_calls_after_scaffold: int
    writing_turns: int
    run_result: RunResult
    scaffold_seconds: float
    feature_seconds: float

    @property
    def total_seconds(self) -> float:
        return self.scaffold_seconds + self.feature_seconds


@pytest.fixture(scope="module")
def greenfield(tmp_path_factory: pytest.TempPathFactory) -> GreenfieldRun:
    """Walk the path once: empty directory, template choice, approval, verified result.

    Module-scoped because it drives the .NET SDK four times over (scaffold build, feature build,
    feature test, plus the restore they share). Every test below reads this one traversal rather
    than repeating it.
    """
    if not registry.get(TEMPLATE_ID).is_built:
        pytest.skip(f"template {TEMPLATE_ID} has no overlay in this checkout")

    root = tmp_path_factory.mktemp("greenfield") / "VersionService"
    provider = ScriptedProvider(json.dumps(EDITS))

    started = time.monotonic()
    scaffold_result = scaffold.execute(scaffold.plan(root, TEMPLATE_ID))
    scaffolded_at = time.monotonic()

    calls_after_scaffold = provider.calls

    run_result = runner.run_approved(
        project=root,
        intent=INTENT,
        provider=provider,
        model="scripted",
        budget=RetryBudget(ceiling=3),
    )
    finished = time.monotonic()

    return GreenfieldRun(
        root=root,
        scaffold_result=scaffold_result,
        provider_calls_after_scaffold=calls_after_scaffold,
        writing_turns=provider.calls,
        run_result=run_result,
        scaffold_seconds=scaffolded_at - started,
        feature_seconds=finished - scaffolded_at,
    )


# --- the scaffold: a working solution before any model is invited to touch it (FR-003) ---------


def test_the_scaffold_builds_before_any_model_runs(greenfield: GreenfieldRun) -> None:
    """FR-003. `scaffold.execute` raises rather than returning a non-building skeleton, so
    reaching this assertion is already most of the proof - it is stated explicitly so that a
    silent change to that contract fails here rather than somewhere downstream.
    """
    assert greenfield.scaffold_result.build.ok, greenfield.scaffold_result.build.combined


def test_the_scaffold_spends_no_model_tokens(greenfield: GreenfieldRun) -> None:
    """SC-012's mechanism. The template is a decision already made, so there is nothing to ask."""
    assert greenfield.provider_calls_after_scaffold == 0


def test_the_scaffold_locks_the_template_choice(greenfield: GreenfieldRun) -> None:
    """The one architecture question a greenfield run asks is answered before any model runs, and
    then recorded - which is why it is never asked again (FR-001c).
    """
    assert state.exists(greenfield.root)
    assert state.load(greenfield.root).template_id == TEMPLATE_ID


def test_the_scaffold_serves_health_on_its_own(greenfield: GreenfieldRun) -> None:
    """The template's health tests drive the real host, so this is the "answers requests" half of
    SC-001 - established by the scaffold, before the feature run adds anything. Both of them must
    execute: one asserts the status code, the other the response body.
    """
    assert_named_tests_pass(greenfield.root, "HealthEndpointTests", expected=2)


def test_no_build_artifacts_reach_the_scaffold(greenfield: GreenfieldRun) -> None:
    """The overlay lives in a working tree where `dotnet format` restores obj/ and bin/, so the
    copy has to filter them - otherwise every generated solution inherits another machine's
    artifacts as its opening state.
    """
    for relative in greenfield.root.rglob("*"):
        parts = relative.relative_to(greenfield.root).parts
        if parts and parts[0] in scaffold.BUILD_ARTIFACT_DIRS:
            pytest.fail(f"build artifact at the solution root: {parts}")


# --- the approved feature: description, one approval, a verified result (SC-001) ---------------


def test_one_approval_yields_a_verified_solution(greenfield: GreenfieldRun) -> None:
    """The headline assertion. `RunOutcome.COMPLETED` means the real `dotnet.verify` returned
    PASS, and PASS means the build was clean *and* every test executed green.
    """
    assert greenfield.run_result.outcome is RunOutcome.COMPLETED, greenfield.run_result.detail


def test_it_compiled_and_tested_on_the_first_attempt(greenfield: GreenfieldRun) -> None:
    """No repair attempt was needed, so the retry budget is untouched (SC-004, SC-007)."""
    result = greenfield.run_result

    assert len(result.attempts) == 1
    assert result.budget.consumed == 0
    verification = result.attempts[0].verification
    assert verification.build is not None and verification.build.ok
    assert verification.test is not None and verification.test.ok


def test_every_edit_applied_without_relaxation(greenfield: GreenfieldRun) -> None:
    """SC-003 asks for at least 90% across runs. A batch anchored on symbols and text the scaffold
    really contains must reach 100%, and must not have needed the relaxation ladder to get there -
    a relaxed anchor still counts for SC-003, but on a solution this pipeline just generated it
    would mean the anchors and the template had drifted apart.
    """
    report = greenfield.run_result.attempts[0].apply_report

    assert report.all_landed, [a.failure_reason for a in report.failed]
    assert report.success_rate == 1.0
    assert len(report.landed) == OPERATION_COUNT
    assert all(a.relaxation_level == RELAXATION_EXACT for a in report.landed)


def test_nothing_is_asked_after_the_template_choice(greenfield: GreenfieldRun) -> None:
    """SC-001. Exactly one writing turn, and the intent that ran is the one that was approved -
    so the developer's only input after picking a template was the approval itself.
    """
    assert greenfield.writing_turns == 1
    assert greenfield.run_result.intent is INTENT


def test_a_repair_cannot_reopen_the_architecture() -> None:
    """FR-020, asserted structurally rather than behaviourally. `Pipeline` is constructed with a
    writer, an applier and a verifier; it holds no architect, so there is no path by which a
    diagnostic could re-decide the design and invalidate the cached prefix.
    """
    assert "architect" not in Pipeline.__dataclass_fields__


def test_the_new_route_is_served_not_merely_compiled(greenfield: GreenfieldRun) -> None:
    """The generated test issues GET /version against the real host. Running it by name proves the
    green result came from the new slice, rather than from the scaffold's health tests passing.
    """
    assert_named_tests_pass(greenfield.root, "VersionEndpointTests", expected=1)


def test_the_served_route_check_would_notice_a_missing_test(greenfield: GreenfieldRun) -> None:
    """Guards the guard. `dotnet test` exits 0 on a filter that matches nothing, so if
    `assert_named_tests_pass` ever stops checking the count, the two "is it served" assertions
    above become assertions about nothing while still reporting green. This proves they fail when
    no test ran.
    """
    with pytest.raises(AssertionError, match="matched no tests"):
        assert_named_tests_pass(greenfield.root, "NoSuchEndpointTests", expected=1)


def test_the_feature_landed_in_the_templates_shape(greenfield: GreenfieldRun) -> None:
    """The template's conventions, not the model's preferences: a feature folder under
    `src/Api/Features`, and exactly one registration line in Program.cs.
    """
    root = greenfield.root

    assert (root / "src/Api/Features/Version/VersionEndpoint.cs").is_file()
    assert (root / "src/Api/Features/Version/VersionResponse.cs").is_file()

    program = (root / "src/Api/Program.cs").read_text(encoding="utf-8")
    assert program.count("app.MapVersion();") == 1
    assert "app.MapHealth();" in program, "the existing slice must survive the edit"


def test_the_untargeted_slice_was_not_rewritten(greenfield: GreenfieldRun) -> None:
    """Only Program.cs was edited among the existing files. The health slice is byte-identical to
    the overlay it came from - the pipeline edits what changes and re-emits nothing else, which is
    the behaviour that keeps a feature's cost proportional to the feature.
    """
    overlay = registry.get(TEMPLATE_ID).overlay_root
    for relative in (
        "src/Api/Features/Health/HealthEndpoint.cs",
        "src/Api/Features/Health/HealthResponse.cs",
    ):
        assert (greenfield.root / relative).read_bytes() == (overlay / relative).read_bytes()


# --- SC-001's offline budget -------------------------------------------------------------------


def test_the_offline_half_of_sc_001_fits_the_budget(greenfield: GreenfieldRun) -> None:
    """SC-001 allows 600 seconds end to end. This is the part that does not vary with the model:
    scaffold, restore, two builds, two test runs, and the edit application. The actual is printed
    so it can be read off a run and carried into the T072 measurement table in baseline.md.
    """
    run = greenfield

    print(
        f"\nSC-001 offline wall clock: scaffold {run.scaffold_seconds:.1f}s + "
        f"feature {run.feature_seconds:.1f}s = {run.total_seconds:.1f}s "
        f"(target < {SC_001_WALL_CLOCK_SECONDS}s including model time)"
    )

    assert run.total_seconds < SC_001_WALL_CLOCK_SECONDS


# --- the gate, against the same scaffolded solution --------------------------------------------


def test_a_rejected_plan_writes_nothing(greenfield: GreenfieldRun) -> None:
    """SC-011's mechanism, asserted offline: a rejection returns before the writer is reached, so
    the writing tokens are never spent and the solution on disk is untouched. The *cost ratio*
    SC-011 states needs a live run - see the T072 procedure in baseline.md.
    """
    before = (greenfield.root / "src/Api/Program.cs").read_bytes()
    unwanted = ChangeIntent(
        summary="Delete the health slice.", target_files=("src/Api/Program.cs",)
    )

    result = Pipeline(
        writer=lambda intent, failure: pytest.fail("the writer ran on a rejected plan"),
        applier=lambda operations: pytest.fail("edits were applied on a rejected plan"),
        verifier=lambda: pytest.fail("verification ran on a rejected plan"),
        budget=RetryBudget(ceiling=3),
    ).run(unwanted, GateDecision.REJECTED)

    assert result.outcome is RunOutcome.REJECTED_AT_GATE
    assert result.attempts == ()
    assert (greenfield.root / "src/Api/Program.cs").read_bytes() == before
