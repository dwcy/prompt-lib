# -*- coding: utf-8 -*-
"""Unit tests for diagnostic parsing and the repair-budget classification rule (T046/T047)."""

from __future__ import annotations

import pytest

from cabal.dotnetgen.verify import dotnet
from cabal.dotnetgen.verify.diagnostics import (
    Classification,
    classify,
    has_test_failures,
    parse,
)

MSBUILD_BUILD_OUTPUT = """
Determining projects to restore...
C:\\src\\Api\\Features\\Orders\\CancelOrder.cs(14,17): error CS0246: The type or namespace name 'IOrderStore' could not be found [C:\\src\\Api\\Api.csproj]
C:\\src\\Api\\Program.cs(9,1): warning CS8602: Dereference of a possibly null reference.
Build FAILED.
"""


def test_parse_extracts_id_prefix_and_file() -> None:
    found = parse(MSBUILD_BUILD_OUTPUT)

    assert [d.id for d in found] == ["CS0246", "CS8602"]


def test_parse_captures_the_message() -> None:
    first = parse(MSBUILD_BUILD_OUTPUT)[0]

    assert "IOrderStore" in first.message


def test_parse_returns_nothing_for_output_with_no_diagnostics() -> None:
    assert parse("Build succeeded.\n    0 Warning(s)\n    0 Error(s)") == ()


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("error NU1101: Unable to find package Foo", Classification.ENVIRONMENT_FAILURE),
        ("error NETSDK1045: The current .NET SDK does not support net10.0", Classification.ENVIRONMENT_FAILURE),
        ("Program.cs(1,1): error CS1002: ; expected", Classification.CODE_DEFECT),
        ("error IDE0005: Using directive is unnecessary", Classification.CODE_DEFECT),
    ],
)
def test_prefix_decides_whether_a_repair_attempt_may_be_spent(
    line: str, expected: Classification
) -> None:
    assert classify(parse(line)) is expected


def test_a_code_defect_anywhere_outranks_environment_noise() -> None:
    """A restore warning alongside a real compiler error must not excuse the compiler error."""
    mixed = "error NU1701: package fallback\nProgram.cs(3,1): error CS0103: name not found"

    assert classify(parse(mixed)) is Classification.CODE_DEFECT


def test_msbuild_error_is_environmental_by_default() -> None:
    assert classify(parse("error MSB4025: invalid project file")) is Classification.ENVIRONMENT_FAILURE


def test_msbuild_error_against_a_file_this_run_wrote_is_repairable() -> None:
    found = parse("src/Api/Api.csproj : error MSB4025: invalid project file")

    assert classify(found, written_files=frozenset({"src/Api/Api.csproj"})) is Classification.CODE_DEFECT


def test_unparseable_failure_never_spends_the_budget() -> None:
    """The toolchain crashed without naming a cause; regenerating C# cannot fix that."""
    assert classify(()) is Classification.ENVIRONMENT_FAILURE


def test_reported_test_failures_are_a_code_defect_even_without_diagnostics() -> None:
    assert classify((), test_failures=True) is Classification.CODE_DEFECT


def _test_output(text: str) -> dotnet.CommandOutput:
    return dotnet.CommandOutput(command=("dotnet", "test"), exit_code=1, stdout=text, stderr="")


def test_has_test_failures_reads_the_reported_count() -> None:
    assert has_test_failures(_test_output("Failed!  - Failed: 2, Passed: 7, Skipped: 0"))


def test_a_zero_failure_count_is_not_a_test_failure() -> None:
    """A non-zero exit with zero failed tests is a harness problem, not a behaviour problem."""
    assert not has_test_failures(_test_output("Passed!  - Failed: 0, Passed: 7"))
