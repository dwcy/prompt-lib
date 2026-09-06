# -*- coding: utf-8 -*-
"""Contract test (T008) for the headless CLI surface consumed by the `/dotnet-codegen` skill.

The skill parses `--json` output, so the exit-code map, the stdout/stderr split and the
argument validation are a wire contract, not internal API. Command bodies land in later
tasks; these assertions cover the surface that exists from Phase 1 onward and must not drift.
"""

from __future__ import annotations

import json

import pytest

from cabal.dotnetgen import cli

ALL_COMMANDS = ("new", "change", "plan", "apply", "map", "report", "providers")

MINIMAL_ARGS = {
    "new": ["new", "--description", "order service"],
    "change": ["change", "--request", "add a cancel endpoint"],
    "plan": ["plan", "--request", "add a cancel endpoint"],
    "apply": ["apply", "--intent-token", "sha256:deadbeef"],
    "map": ["map"],
    "report": ["report"],
    "providers": ["providers"],
}


def test_exit_code_map_matches_the_contract() -> None:
    assert cli.EXIT_OK == 0
    assert cli.EXIT_FAILURE == 1
    assert cli.EXIT_USAGE == 2
    assert cli.EXIT_HALTED_AT_CEILING == 3
    assert cli.EXIT_ENVIRONMENT_FAILURE == 4
    assert cli.EXIT_REJECTED_AT_GATE == 5


def test_template_ids_are_the_closed_set_of_three() -> None:
    assert cli.TEMPLATE_IDS == ("minimal-service", "vertical-slice", "clean-arch")
    assert cli.DEFAULT_TEMPLATE in cli.TEMPLATE_IDS


def test_retry_ceiling_defaults_to_three() -> None:
    assert cli.DEFAULT_RETRY_CEILING == 3


@pytest.mark.parametrize("command", ALL_COMMANDS)
def test_every_command_accepts_the_global_options(command: str) -> None:
    argv = [*MINIMAL_ARGS[command], "--json", "--project", ".", "--dry-run", "--retry-ceiling", "5"]
    args = cli.build_parser().parse_args(argv)
    assert args.command == command
    assert args.json is True
    assert args.dry_run is True
    assert args.retry_ceiling == 5


def test_no_command_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == cli.EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.out == "", "usage help must not pollute stdout"
    assert "COMMAND" in captured.err


def test_unknown_template_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["new", "--template", "hexagonal", "--description", "x"])
    assert excinfo.value.code == cli.EXIT_USAGE


def test_unknown_template_error_lists_the_closed_set(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["new", "--template", "hexagonal", "--description", "x"])
    message = capsys.readouterr().err
    for template in cli.TEMPLATE_IDS:
        assert template in message, "an unknown template must never silently fall back"


def test_missing_required_argument_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["new"])
    assert excinfo.value.code == cli.EXIT_USAGE


def test_negative_retry_ceiling_is_a_usage_error() -> None:
    assert cli.main(["change", "--request", "x", "--retry-ceiling", "-1"]) == cli.EXIT_USAGE


@pytest.mark.parametrize("command", ALL_COMMANDS)
def test_json_mode_emits_exactly_one_object_on_stdout(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main([*MINIMAL_ARGS[command], "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert isinstance(payload, dict)
    assert captured.out.count("\n") == 1, "exactly one JSON object, one trailing newline"


@pytest.mark.parametrize("command", ALL_COMMANDS)
def test_human_mode_keeps_stdout_clean(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(MINIMAL_ARGS[command])
    captured = capsys.readouterr()
    assert captured.out == "", "human output belongs on stderr"
    assert captured.err.strip() != ""


@pytest.mark.parametrize("command", ALL_COMMANDS)
def test_unwired_commands_report_their_owning_task(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Deferral is explicit and discoverable: the error names the task that implements it.

    Wired commands are excluded by consulting the handler registry rather than by inspecting an
    exit code - a wired command can legitimately fail for its own reasons, and reading that as
    "still unwired" would make this assertion outlive the deferral it describes.
    """
    if command in cli._HANDLERS:
        pytest.skip(f"`{command}` is now wired; this assertion retires with it")
    code = cli.main([*MINIMAL_ARGS[command], "--json"])
    assert code != cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert "not wired yet" in payload["error"]
    assert "T0" in payload["error"]


def test_version_line_reports_the_package_version() -> None:
    from cabal.dotnetgen import __version__

    assert cli.version_line() == f"cabal.dotnetgen {__version__}"
