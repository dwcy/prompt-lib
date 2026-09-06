# -*- coding: utf-8 -*-
"""Contract test (T040) for the structural map: the budget must never truncate silently.

FR-006 and US6's second scenario turn on one rule. A map that stops at its budget and says
nothing is indistinguishable from a complete one, so the model reasons about a solution it
believes it has seen in full and asks for files the map never mentioned. Reporting the omission
is what makes the budget a boundary rather than a lie.

The map is also cache band 3, so byte-identical output for an unchanged solution is a contract,
not an optimisation - a map that differs by a reordered line invalidates everything cached below.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal.dotnetgen import cli, map_cache
from cabal.dotnetgen.context.structural_map import build

TYPE_TEMPLATE = """namespace Sample.Generated;

public sealed class Type{index}
{{
    public void Method{index}(int value)
    {{
        Total = value;
    }}
}}
"""


@pytest.fixture
def many_types(solution_dir: Path) -> Path:
    source = solution_dir / "src" / "Api"
    source.mkdir(parents=True)
    for index in range(40):
        (source / f"Type{index}.cs").write_text(
            TYPE_TEMPLATE.format(index=index), encoding="utf-8"
        )
    return solution_dir


def test_a_generous_budget_omits_nothing(many_types: Path) -> None:
    built = build(many_types, fingerprint="sha256:test", token_budget=100_000)

    assert built.omitted_count == 0
    assert built.omitted_summary is None


def test_a_binding_budget_reports_what_it_dropped(many_types: Path) -> None:
    built = build(many_types, fingerprint="sha256:test", token_budget=60)

    assert built.omitted_count > 0, "a 60-token budget cannot hold 40 types"
    assert built.omitted_summary is not None, "silent truncation is the defect this test exists for"
    assert str(built.omitted_count) in built.omitted_summary


def test_the_omission_is_visible_in_the_rendered_map(many_types: Path) -> None:
    built = build(many_types, fingerprint="sha256:test", token_budget=60)

    assert "[omitted]" in built.render()


def test_a_binding_budget_still_returns_something(many_types: Path) -> None:
    """Dropping everything would be a different failure: the model gets no map at all."""
    built = build(many_types, fingerprint="sha256:test", token_budget=1)

    assert len(built.entries) >= 1


def test_the_map_never_contains_a_member_body(many_types: Path) -> None:
    rendered = build(many_types, fingerprint="sha256:test", token_budget=100_000).render()

    assert "Total = value" not in rendered, "bodies are the token waste the map exists to avoid"


def test_an_unchanged_solution_yields_byte_identical_output(many_types: Path) -> None:
    first, _ = map_cache.rendered_map(many_types, token_budget=100_000)
    second, _ = map_cache.rendered_map(many_types, token_budget=100_000)

    assert first == second


def test_the_map_command_reports_the_omission_on_the_json_channel(
    many_types: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = cli.main(["map", "--project", str(many_types), "--budget", "60", "--json"])

    assert exit_code == cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["omitted_count"] > 0
    assert payload["omitted_summary"]
