# -*- coding: utf-8 -*-
"""T014/T016: what discovery finds, what it refuses to descend into, and how bad files degrade."""

from __future__ import annotations

import json
from pathlib import Path

from cabal.envsource_discovery import (
    MAX_FILE_BYTES,
    AvailabilityState,
    build_file_source,
    collect_repo_files,
    discover_config_files,
    read_keys,
    read_value,
)


def _labels(project: Path) -> set[str]:
    files, _notices = discover_config_files(project)
    return {item.relative for item in files}


def test_files_excluded_from_version_control_are_still_listed(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env.local\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("SECRET_URL=x\n", encoding="utf-8")

    assert ".env.local" in _labels(tmp_path)


def test_dependency_and_build_directories_are_never_descended_into(tmp_path: Path) -> None:
    for directory in ("node_modules", "__pycache__", "dist", ".git", "obj", ".venv"):
        nested = tmp_path / directory / "inner"
        nested.mkdir(parents=True)
        (nested / ".env").write_text("HIDDEN=1\n", encoding="utf-8")
    (tmp_path / ".env").write_text("VISIBLE=1\n", encoding="utf-8")

    assert _labels(tmp_path) == {".env"}


def test_the_depth_cap_holds(tmp_path: Path) -> None:
    deep = tmp_path
    for level in range(8):
        deep = deep / f"level{level}"
    deep.mkdir(parents=True)
    (deep / ".env").write_text("TOO_DEEP=1\n", encoding="utf-8")

    files, _notices = discover_config_files(tmp_path, max_depth=3)

    assert files == []


def test_the_file_cap_is_reported_rather_than_silently_truncating(tmp_path: Path) -> None:
    for index in range(6):
        (tmp_path / f".env.app{index}").write_text("KEY=1\n", encoding="utf-8")

    files, notices = discover_config_files(tmp_path, max_files=3)

    assert len(files) == 3
    assert notices and "3" in notices[0]


def test_the_discovery_patterns_cover_the_documented_set(tmp_path: Path) -> None:
    names = [
        ".env",
        ".env.local",
        ".env.production",
        "appsettings.json",
        "appsettings.Development.json",
        "config.env.json",
        "production.env",
    ]
    for name in names:
        (tmp_path / name).write_text("{}" if name.endswith(".json") else "K=1\n", encoding="utf-8")
    properties = tmp_path / "Properties"
    properties.mkdir()
    (properties / "launchSettings.json").write_text("{}", encoding="utf-8")
    (tmp_path / "README.md").write_text("not config", encoding="utf-8")

    found = _labels(tmp_path)

    assert set(names) <= found
    assert "Properties/launchSettings.json" in found
    assert "README.md" not in found


def test_same_named_files_across_a_monorepo_stay_distinguishable(tmp_path: Path) -> None:
    for service in ("billing", "shipping"):
        directory = tmp_path / "services" / service
        directory.mkdir(parents=True)
        (directory / "appsettings.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".env").write_text("K=1\n", encoding="utf-8")

    files, _notices = discover_config_files(tmp_path)
    keyed = {(item.label, item.qualifier) for item in files}

    assert len(keyed) == len(files)
    assert ("appsettings.json", "services/billing") in keyed
    assert ("appsettings.json", "services/shipping") in keyed
    # A name that is already unique carries no qualifier — nothing to disambiguate.
    assert (".env", None) in keyed


# -- parsing -------------------------------------------------------------


def test_an_empty_file_reports_empty_rather_than_failing(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("", encoding="utf-8")

    keys, state, hint = read_keys(path)

    assert keys == []
    assert state is AvailabilityState.EMPTY
    assert hint is None


def test_a_comments_only_file_is_empty_not_unreadable(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("# just a note\n\n#  another\n", encoding="utf-8")

    keys, state, _hint = read_keys(path)

    assert keys == []
    assert state is AvailabilityState.EMPTY


def test_a_malformed_json_file_degrades_with_a_stated_reason(tmp_path: Path) -> None:
    path = tmp_path / "appsettings.json"
    path.write_text("{ not json", encoding="utf-8")

    keys, state, hint = read_keys(path)

    assert keys == []
    assert state is AvailabilityState.DEGRADED
    assert "appsettings.json" in hint and "JSON" in hint


def test_a_duplicate_key_is_one_row(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("PORT=1\nPORT=2\nHOST=a\n", encoding="utf-8")

    keys, state, _hint = read_keys(path)

    assert keys == ["PORT", "HOST"]
    assert state is AvailabilityState.OK


def test_a_bad_file_does_not_affect_its_siblings(tmp_path: Path) -> None:
    (tmp_path / "appsettings.json").write_text("{ broken", encoding="utf-8")
    (tmp_path / ".env").write_text("GOOD=1\n", encoding="utf-8")

    sources, _notices = collect_repo_files(tmp_path)
    by_label = {source.label: source for source in sources}

    assert by_label["appsettings.json"].state is AvailabilityState.DEGRADED
    assert by_label[".env"].state is AvailabilityState.OK
    assert by_label[".env"].containers[0].entries[0].name == "GOOD"


def test_export_prefixes_and_quoted_values_are_understood(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text('export TOKEN="abc def"\nPLAIN=1\n', encoding="utf-8")

    keys, _state, _hint = read_keys(path)

    assert keys == ["TOKEN", "PLAIN"]
    assert read_value(path, "TOKEN") == "abc def"


def test_a_file_larger_than_the_cap_degrades_rather_than_being_parsed(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("K=" + "x" * (MAX_FILE_BYTES + 10), encoding="utf-8")

    _keys, state, hint = read_keys(path)

    assert state is AvailabilityState.DEGRADED
    assert "larger than" in hint


def test_a_degraded_file_source_exposes_no_container_to_read_from(tmp_path: Path) -> None:
    path = tmp_path / "appsettings.json"
    path.write_text("{ broken", encoding="utf-8")
    files, _notices = discover_config_files(tmp_path)

    source = build_file_source(files[0])

    assert source.state is AvailabilityState.DEGRADED
    assert source.containers == []


def test_reveal_reads_the_literal_value_for_json_and_dotenv(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("DATABASE_URL=postgres://x\n", encoding="utf-8")
    settings = tmp_path / "appsettings.json"
    settings.write_text(json.dumps({"Logging": {"LogLevel": {"Default": "Warning"}}}), encoding="utf-8")

    assert read_value(dotenv, "DATABASE_URL") == "postgres://x"
    assert read_value(settings, "Logging:LogLevel:Default") == "Warning"
    assert read_value(dotenv, "ABSENT") is None
