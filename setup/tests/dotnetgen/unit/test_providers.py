# -*- coding: utf-8 -*-
"""Unit tests for usage normalisation, the provider factory, and the CLI-shell helpers."""

from __future__ import annotations

import json

import pytest

from types import SimpleNamespace

from cabal.dotnetgen.providers import cli_shell, factory, usage
from cabal.dotnetgen.providers.base import Message, ProviderError, Usage
from cabal.dotnetgen.providers.config import StageBinding
from cabal.dotnetgen.providers.openai_compatible import OpenAICompatibleProvider

# --- usage normalisation -------------------------------------------------------------------


def test_anthropic_input_total_includes_cache_traffic() -> None:
    """`input_tokens` excludes cache reads and writes, so the true total is additive."""
    parsed = usage.parse_usage(
        {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_input_tokens": 900,
            "cache_creation_input_tokens": 0,
        }
    )

    assert parsed.input_tokens == 1000


def test_anthropic_cache_ratio_is_computed_from_the_full_input() -> None:
    parsed = usage.parse_usage(
        {"input_tokens": 100, "output_tokens": 5, "cache_read_input_tokens": 900}
    )

    assert parsed.cache_ratio == pytest.approx(0.9)


def test_openai_prompt_tokens_are_not_double_counted() -> None:
    """`prompt_tokens` already includes `cached_tokens`; adding them would inflate the total."""
    parsed = usage.parse_usage(
        {
            "prompt_tokens": 1000,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 900},
        }
    )

    assert parsed.input_tokens == 1000


def test_openai_cached_tokens_are_recorded() -> None:
    parsed = usage.parse_usage(
        {"prompt_tokens": 1000, "prompt_tokens_details": {"cached_tokens": 900}}
    )

    assert parsed.cached_input_tokens == 900


def test_flattened_cached_tokens_are_accepted() -> None:
    """Some OpenAI-compatible proxies flatten the details object."""
    parsed = usage.parse_usage({"prompt_tokens": 500, "cached_tokens": 100})

    assert parsed.cached_input_tokens == 100


def test_absent_cache_field_is_reported_as_unmeasured() -> None:
    """A zero must never masquerade as a measurement - SC-005 depends on the distinction."""
    parsed = usage.parse_usage({"prompt_tokens": 100, "completion_tokens": 10})

    assert parsed.cache_reported is False


def test_unmeasured_cache_yields_no_ratio() -> None:
    parsed = usage.parse_usage({"prompt_tokens": 100})

    assert parsed.cache_ratio is None


def test_missing_usage_object_is_reported_as_unmeasured() -> None:
    assert usage.parse_usage(None).cache_reported is False


def test_uncached_input_is_derived_from_the_totals() -> None:
    parsed = usage.parse_usage({"prompt_tokens": 1000, "prompt_tokens_details": {"cached_tokens": 250}})

    assert parsed.uncached_input_tokens == 750


def test_usage_addition_preserves_unmeasured_caching() -> None:
    """Summing a measured and an unmeasured call must not claim the total is measured."""
    total = Usage(input_tokens=10, cache_reported=True) + Usage(input_tokens=5, cache_reported=False)

    assert total.cache_reported is False


# --- provider factory ----------------------------------------------------------------------


def test_cli_shell_binding_builds_a_cli_provider() -> None:
    binding = StageBinding(stage="architect", provider="cli_shell", model="claude-opus-5")

    assert isinstance(factory.provider_for(binding), cli_shell.CliShellProvider)


def test_openai_compatible_binding_builds_an_http_provider() -> None:
    binding = StageBinding(
        stage="write", provider="openai_compatible", model="m", base_url="http://localhost:11434/v1"
    )

    assert isinstance(factory.provider_for(binding), OpenAICompatibleProvider)


def test_anthropic_binding_builds_its_adapter() -> None:
    binding = StageBinding(stage="architect", provider="anthropic", model="m")

    assert factory.provider_for(binding).name == "anthropic"


def test_google_binding_builds_its_adapter() -> None:
    binding = StageBinding(stage="architect", provider="google", model="m")

    assert factory.provider_for(binding).name == "google"


def test_unknown_provider_is_refused() -> None:
    binding = StageBinding(stage="write", provider="tarot", model="m")

    with pytest.raises(ProviderError):
        factory.provider_for(binding)


# --- local endpoint detection (SC-008) ------------------------------------------------------


@pytest.mark.parametrize(
    "base_url",
    ["http://localhost:11434/v1", "http://127.0.0.1:1234/v1", "http://0.0.0.0:8080/v1"],
    ids=["ollama", "lm-studio", "bound-all"],
)
def test_local_endpoints_are_recognised_as_zero_cost(base_url: str) -> None:
    binding = StageBinding(stage="write", provider="openai_compatible", model="m", base_url=base_url)

    assert OpenAICompatibleProvider(binding=binding).is_local is True


def test_hosted_endpoint_is_not_local() -> None:
    binding = StageBinding(
        stage="write", provider="openai_compatible", model="m", base_url="https://api.openai.com/v1"
    )

    assert OpenAICompatibleProvider(binding=binding).is_local is False


def test_binding_without_base_url_is_an_error() -> None:
    binding = StageBinding(stage="write", provider="openai_compatible", model="m")

    with pytest.raises(ProviderError):
        _ = OpenAICompatibleProvider(binding=binding).base_url


# --- CLI selection and stream-json extraction ----------------------------------------------


@pytest.mark.parametrize("model", ["claude-opus-5", "claude-haiku-4-5-20251001"])
def test_claude_models_route_to_the_claude_cli(model: str) -> None:
    assert cli_shell.resolve_cli(model) == "claude"


@pytest.mark.parametrize("model", ["gpt-5", "o3-mini"])
def test_openai_models_route_to_the_codex_cli(model: str) -> None:
    assert cli_shell.resolve_cli(model) == "codex"


def test_unrecognised_model_id_is_refused() -> None:
    with pytest.raises(cli_shell.CliShellError):
        cli_shell.resolve_cli("mystery-model-1")


def test_claude_flags_request_stream_json_with_verbose() -> None:
    """`--print` with `--output-format stream-json` errors out unless `--verbose` is present."""
    assert "--verbose" in cli_shell.CLAUDE_FLAGS


def test_claude_flags_forbid_the_model_writing_files() -> None:
    """The pipeline orchestrates writes; the CLI session must never touch the filesystem."""
    assert "plan" in cli_shell.CLAUDE_FLAGS


def test_result_event_yields_its_text() -> None:
    text, _usage, _cost = cli_shell.extract_result(
        {"type": "result", "subtype": "success", "is_error": False, "result": "hello"}
    )

    assert text == "hello"


def test_result_event_usage_is_normalised() -> None:
    _text, parsed, _cost = cli_shell.extract_result(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "ok",
            "usage": {"input_tokens": 10, "output_tokens": 4, "cache_read_input_tokens": 90},
        }
    )

    assert parsed.cached_input_tokens == 90


def test_result_event_cost_is_read() -> None:
    _text, _usage, cost = cli_shell.extract_result(
        {"type": "result", "subtype": "success", "is_error": False, "result": "ok", "total_cost_usd": 0.02}
    )

    assert cost == pytest.approx(0.02)


def test_error_flagged_result_raises() -> None:
    with pytest.raises(cli_shell.CliShellError):
        cli_shell.extract_result({"type": "result", "is_error": True, "result": "boom"})


def test_non_success_subtype_raises() -> None:
    with pytest.raises(cli_shell.CliShellError):
        cli_shell.extract_result({"type": "result", "subtype": "error_max_turns", "result": "x"})


def test_result_without_text_raises() -> None:
    with pytest.raises(cli_shell.CliShellError):
        cli_shell.extract_result({"type": "result", "subtype": "success", "is_error": False})


def test_flattening_keeps_user_content_verbatim() -> None:
    flat = cli_shell.flatten((Message(role="user", content="add an endpoint"),))

    assert flat == "add an endpoint"


def test_flattening_labels_non_user_roles() -> None:
    flat = cli_shell.flatten(
        (Message(role="system", content="rules"), Message(role="user", content="do it"))
    )

    assert flat == "[system]\nrules\n\ndo it"


def test_a_timed_out_turn_tears_down_the_session_so_no_stale_result_survives() -> None:
    """The CLI keeps working after a timeout; reusing the session would answer the next prompt with it."""
    session = cli_shell.ClaudeSession(model="claude-sonnet-4", executable="claude")
    closed: list[bool] = []
    session.start = lambda: None  # type: ignore[method-assign]
    session.close = lambda: closed.append(True)  # type: ignore[method-assign]
    session._process = SimpleNamespace(stdin=SimpleNamespace(write=lambda _t: None, flush=lambda: None))
    session._lines.put(json.dumps({"type": "result", "result": "stale answer"}))

    with pytest.raises(cli_shell.CliShellError):
        session.send("prompt", timeout=0)

    assert closed == [True]
    assert session._lines.empty()


def test_an_oversized_codex_prompt_is_reported_as_a_prompt_problem() -> None:
    """An argv-length failure must not masquerade as the provider being unreachable."""
    binding = StageBinding(stage="architect", provider="cli_shell", model="gpt-5-codex")
    provider = cli_shell.CliShellProvider(binding=binding)

    with pytest.raises(cli_shell.CliShellError, match="command-line budget"):
        provider._codex_turn("x" * (cli_shell._MAX_CODEX_PROMPT_CHARS + 1))
