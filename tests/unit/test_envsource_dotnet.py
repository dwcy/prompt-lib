# -*- coding: utf-8 -*-
"""T036/T039/T042/T043: .NET key flattening, layer precedence, launch profiles, secret store."""

from __future__ import annotations

import json
from pathlib import Path

from cabal.envsource_discovery import collect_repo_files
from cabal.envsource_dotnet import (
    RANK_BASE_SETTINGS,
    RANK_ENVIRONMENT_SETTINGS,
    AvailabilityState,
    find_user_secrets,
    flatten_json_keys,
    layer_for,
    lookup_flattened,
    user_secrets_store,
)


def _by_label(project: Path) -> dict:
    sources, _notices = collect_repo_files(project)
    return {source.label: source for source in sources}


def _write(path: Path, document) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


# -- flattening ----------------------------------------------------------


def test_nested_sections_flatten_to_fully_qualified_leaf_paths() -> None:
    document = {"Logging": {"LogLevel": {"Default": "Information", "System": "Warning"}}}

    assert flatten_json_keys(document) == ["Logging:LogLevel:Default", "Logging:LogLevel:System"]


def test_a_section_containing_only_sections_is_not_listed_as_a_key() -> None:
    keys = flatten_json_keys({"Logging": {"LogLevel": {"Default": "Information"}}})

    assert "Logging" not in keys
    assert "Logging:LogLevel" not in keys


def test_arrays_address_each_element_by_index() -> None:
    document = {"Cors": {"Origins": ["https://a.test", "https://b.test"]}}

    assert flatten_json_keys(document) == ["Cors:Origins:0", "Cors:Origins:1"]


def test_deep_nesting_stays_addressable() -> None:
    document = {"A": {"B": {"C": {"D": {"E": 1}}}}}

    assert flatten_json_keys(document) == ["A:B:C:D:E"]


def test_an_empty_object_is_a_leaf_because_the_framework_binds_it() -> None:
    assert flatten_json_keys({"Feature": {}, "Flags": []}) == ["Feature", "Flags"]


def test_a_flattened_path_resolves_back_to_its_literal_value() -> None:
    document = {"Cors": {"Origins": ["https://a.test"]}, "Debug": True, "Port": 8080}

    assert lookup_flattened(document, "Cors:Origins:0") == "https://a.test"
    assert lookup_flattened(document, "Debug") == "true"
    assert lookup_flattened(document, "Port") == "8080"
    assert lookup_flattened(document, "Cors:Missing") is None


# -- precedence ----------------------------------------------------------


def test_the_environment_specific_layer_outranks_the_base_layer() -> None:
    base = layer_for("appsettings.json")
    development = layer_for("appsettings.Development.json")

    assert base.rank == RANK_BASE_SETTINGS
    assert development.rank == RANK_ENVIRONMENT_SETTINGS
    assert development.rank < base.rank
    assert layer_for(".env") is None


def test_a_key_defined_in_both_layers_names_the_environment_layer_as_the_winner(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "appsettings.json", {"ConnectionStrings": {"Db": "base"}})
    _write(tmp_path / "appsettings.Development.json", {"ConnectionStrings": {"Db": "dev"}})

    sources = _by_label(tmp_path)
    base = sources["appsettings.json"].containers[0]
    development = sources["appsettings.Development.json"].containers[0]

    assert development.layer.wins is True
    assert base.layer.wins is False


def test_the_rows_stay_separate_and_no_merged_value_is_produced(tmp_path: Path) -> None:
    _write(tmp_path / "appsettings.json", {"ConnectionStrings": {"Db": "base"}})
    _write(tmp_path / "appsettings.Development.json", {"ConnectionStrings": {"Db": "dev"}})

    sources = _by_label(tmp_path)
    names = [
        entry.name
        for label in ("appsettings.json", "appsettings.Development.json")
        for container in sources[label].containers
        for entry in container.entries
    ]

    assert names == ["ConnectionStrings:Db", "ConnectionStrings:Db"]
    assert all(not hasattr(entry, "value") for entry in sources["appsettings.json"].containers[0].entries)


def test_two_environment_layers_that_never_load_together_declare_no_winner(tmp_path: Path) -> None:
    _write(tmp_path / "appsettings.Development.json", {"Key": "dev"})
    _write(tmp_path / "appsettings.Production.json", {"Key": "prod"})

    sources = _by_label(tmp_path)

    assert sources["appsettings.Development.json"].containers[0].layer.wins is False
    assert sources["appsettings.Production.json"].containers[0].layer.wins is False


def test_precedence_is_computed_per_project_directory_not_across_a_monorepo(tmp_path: Path) -> None:
    _write(tmp_path / "services" / "a" / "appsettings.json", {"Key": "a"})
    _write(tmp_path / "services" / "b" / "appsettings.Development.json", {"Key": "b"})

    sources = _by_label(tmp_path)

    # Neither is beaten by the other: they belong to different applications, so the
    # environment-specific file in service b does not outrank the base file in service a.
    assert sources["appsettings.json"].containers[0].layer.wins is True
    assert sources["appsettings.Development.json"].containers[0].layer.wins is True


# -- launch profiles -----------------------------------------------------


def test_launch_profile_variables_are_attributed_to_their_profile(tmp_path: Path) -> None:
    _write(
        tmp_path / "Properties" / "launchSettings.json",
        {
            "profiles": {
                "http": {"environmentVariables": {"ASPNETCORE_ENVIRONMENT": "Development"}},
                "https": {"environmentVariables": {"ASPNETCORE_ENVIRONMENT": "Staging"}},
                "IIS Express": {"commandName": "IISExpress"},
            }
        },
    )

    source = _by_label(tmp_path)["launchSettings.json"]
    by_profile = {container.label: container for container in source.containers}

    assert set(by_profile) == {"http", "https"}
    assert by_profile["http"].entries[0].target == "http"
    assert by_profile["http"].entries[0].name == "ASPNETCORE_ENVIRONMENT"


def test_a_launch_settings_file_with_no_variables_is_empty_not_broken(tmp_path: Path) -> None:
    _write(tmp_path / "Properties" / "launchSettings.json", {"profiles": {"http": {}}})

    source = _by_label(tmp_path)["launchSettings.json"]

    assert source.state is AvailabilityState.EMPTY
    assert source.containers == []


# -- developer secret store ----------------------------------------------


def _project_with_secrets_id(tmp_path: Path, secrets_id: str) -> Path:
    project_file = tmp_path / "Api" / "Api.csproj"
    project_file.parent.mkdir(parents=True, exist_ok=True)
    project_file.write_text(
        f"<Project><PropertyGroup><UserSecretsId>{secrets_id}</UserSecretsId>"
        "</PropertyGroup></Project>",
        encoding="utf-8",
    )
    return project_file


def test_a_store_is_read_only_when_the_selected_project_declares_its_id(tmp_path: Path) -> None:
    _project_with_secrets_id(tmp_path, "abc-123")

    declarations = find_user_secrets(tmp_path)

    assert [item.secrets_id for item in declarations] == ["abc-123"]
    assert declarations[0].project_file == "Api/Api.csproj"


def test_a_project_declaring_no_store_yields_no_declaration_and_no_error(tmp_path: Path) -> None:
    (tmp_path / "Api.csproj").write_text("<Project></Project>", encoding="utf-8")

    assert find_user_secrets(tmp_path) == []


def test_the_secrets_directory_is_never_enumerated(tmp_path: Path, monkeypatch) -> None:
    """FR-047: the id must come from the project; the store root is never listed."""
    import cabal.envsource_dotnet as module

    _project_with_secrets_id(tmp_path, "abc-123")
    listed: list[Path] = []
    original = Path.iterdir

    def watched(self):
        listed.append(self)
        return original(self)

    monkeypatch.setattr(Path, "iterdir", watched)
    find_user_secrets(tmp_path)

    store_root = module.user_secrets_store("abc-123").parent.parent
    assert all(store_root != directory for directory in listed)


def test_an_id_that_could_escape_the_store_root_is_refused(tmp_path: Path) -> None:
    _project_with_secrets_id(tmp_path, "../../elsewhere")

    assert find_user_secrets(tmp_path) == []


def test_a_declared_but_never_created_store_reports_empty_not_an_error(
    tmp_path: Path, monkeypatch
) -> None:
    import cabal.envsource_dotnet as module

    _project_with_secrets_id(tmp_path, "never-created")
    monkeypatch.setattr(module, "user_secrets_store", lambda sid: tmp_path / "nowhere" / sid / "secrets.json")

    source = _by_label(tmp_path)["User secrets"]

    assert source.state is AvailabilityState.EMPTY
    assert source.hint is None
    assert source.outside_repository is True


def test_a_populated_store_is_its_own_badged_source(tmp_path: Path, monkeypatch) -> None:
    import cabal.envsource_dotnet as module

    _project_with_secrets_id(tmp_path, "abc-123")
    store = tmp_path / "store" / "secrets.json"
    _write(store, {"ConnectionStrings": {"Db": "Server=."}})
    monkeypatch.setattr(module, "user_secrets_store", lambda _sid: store)

    source = _by_label(tmp_path)["User secrets"]

    assert source.state is AvailabilityState.OK
    assert source.outside_repository is True
    assert [entry.name for entry in source.containers[0].entries] == ["ConnectionStrings:Db"]


def test_the_store_path_follows_the_platform_convention() -> None:
    store = user_secrets_store("abc-123")

    assert store.name == "secrets.json"
    assert store.parent.name == "abc-123"
    assert store.parent.parent.name.lower() in {"usersecrets"}
