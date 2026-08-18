# -*- coding: utf-8 -*-
"""Unit tests for stage-binding resolution, including that the shipped config actually parses."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from cabal.dotnetgen.providers import config

VALID = """
[defaults]
retry_ceiling = 3
map_token_budget = 1024

[stages.route]
provider = "openai_compatible"
model = "local-small"
base_url = "http://localhost:11434/v1"

[stages.architect]
provider = "cli_shell"
model = "big"

[stages.architect.fallback]
provider = "anthropic"
model = "medium"
api_key_env = "ANTHROPIC_API_KEY"

[stages.write]
provider = "openai_compatible"
model = "local-small"
base_url = "http://localhost:11434/v1"
"""


def _parse(text: str) -> config.Bindings:
    return config.parse_bindings(tomllib.loads(text))


# --- the shipped file ----------------------------------------------------------------------


def test_shipped_bindings_file_parses() -> None:
    """The file deployed to ~/.claude must be valid; a broken default config blocks every run."""
    assert config.REPO_BINDINGS_PATH.is_file(), config.REPO_BINDINGS_PATH

    bindings = config.parse_bindings(tomllib.loads(config.REPO_BINDINGS_PATH.read_text(encoding="utf-8")))

    assert set(bindings.stages) == set(config.MODEL_STAGES)


def test_shipped_bindings_file_contains_no_secrets() -> None:
    """Names only. A key committed here would be a key published to every machine."""
    text = config.REPO_BINDINGS_PATH.read_text(encoding="utf-8").lower()

    assert "sk-" not in text and "api_key =" not in text


def test_shipped_bindings_default_ceiling_is_three() -> None:
    bindings = config.parse_bindings(tomllib.loads(config.REPO_BINDINGS_PATH.read_text(encoding="utf-8")))

    assert bindings.retry_ceiling == 3


# --- parsing -------------------------------------------------------------------------------


def test_every_model_stage_resolves_to_a_binding() -> None:
    bindings = _parse(VALID)

    assert [bindings.for_stage(s).stage for s in config.MODEL_STAGES] == list(config.MODEL_STAGES)


def test_verify_stage_has_no_binding() -> None:
    """`verify` runs the .NET toolchain, not a model - the free signal."""
    bindings = _parse(VALID)

    with pytest.raises(config.BindingsError):
        bindings.for_stage("verify")


def test_a_verify_stage_table_is_rejected() -> None:
    with pytest.raises(config.BindingsError):
        _parse(VALID + '\n[stages.verify]\nprovider = "x"\nmodel = "y"\n')


def test_fallback_is_parsed_as_a_binding() -> None:
    fallback = _parse(VALID).for_stage("architect").fallback

    assert (fallback.provider, fallback.model) == ("anthropic", "medium")


def test_missing_stage_table_is_rejected() -> None:
    without_write = VALID.split("[stages.write]")[0]

    with pytest.raises(config.BindingsError):
        _parse(without_write)


def test_stage_without_a_model_is_rejected() -> None:
    with pytest.raises(config.BindingsError):
        _parse(VALID.replace('model = "big"', ""))


def test_negative_retry_ceiling_is_rejected() -> None:
    with pytest.raises(config.BindingsError):
        _parse(VALID.replace("retry_ceiling = 3", "retry_ceiling = -1"))


def test_zero_map_budget_is_rejected() -> None:
    with pytest.raises(config.BindingsError):
        _parse(VALID.replace("map_token_budget = 1024", "map_token_budget = 0"))


# --- api keys ------------------------------------------------------------------------------


def test_binding_without_api_key_env_needs_no_key() -> None:
    assert _parse(VALID).for_stage("architect").requires_api_key is False


def test_api_key_is_read_from_the_environment_not_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    fallback = _parse(VALID).for_stage("architect").fallback

    assert fallback.api_key() == "from-env"


def test_absent_environment_key_is_reported_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fallback = _parse(VALID).for_stage("architect").fallback

    assert fallback.missing_key() is True


# --- resolution order ----------------------------------------------------------------------


def test_project_override_wins_over_the_machine_file(tmp_path: Path) -> None:
    project = tmp_path / "solution"
    (project / ".dotnetgen").mkdir(parents=True)
    override = project / config.PROJECT_BINDINGS_RELPATH
    override.write_text(VALID.replace('model = "big"', 'model = "project-specific"'), encoding="utf-8")

    bindings = config.load_bindings(project, search=(override, config.REPO_BINDINGS_PATH))

    assert bindings.for_stage("architect").model == "project-specific"


def test_project_path_is_searched_before_the_machine_path(tmp_path: Path) -> None:
    ordered = config.default_search_paths(tmp_path / "solution")

    assert ordered[0].parts[-2:] == (".dotnetgen", "bindings.toml")


def test_missing_bindings_everywhere_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(config.BindingsError):
        config.load_bindings(search=(tmp_path / "nope.toml",))


def test_rebinding_a_stage_leaves_the_others_untouched() -> None:
    bindings = _parse(VALID)
    local = config.StageBinding(stage="write", provider="openai_compatible", model="other-local")

    rebound = config.override_stage(bindings, "write", local)

    assert (rebound.for_stage("write").model, rebound.for_stage("route").model) == ("other-local", "local-small")


def test_rebinding_an_unknown_stage_is_rejected() -> None:
    binding = config.StageBinding(stage="verify", provider="x", model="y")

    with pytest.raises(config.BindingsError):
        config.override_stage(_parse(VALID), "verify", binding)
