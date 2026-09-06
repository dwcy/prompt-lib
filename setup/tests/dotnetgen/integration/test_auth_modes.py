# -*- coding: utf-8 -*-
"""Integration test (T059) for the three auth modes a stage can be bound to.

The pipeline has to work for developers with different arrangements, and the three are genuinely
different mechanisms rather than three spellings of one:

  subscription  the `claude` / `codex` CLIs, authenticated by an existing login, no key anywhere
  API key       read from the environment at call time, never written to the bindings file
  local         an endpoint on this machine, no key and no per-token cost

Each must resolve through the same seam, report usage in the same shape, and fall back the same
way. No network is touched: what is under test is resolution and normalisation, not connectivity.
"""

from __future__ import annotations

import pytest

from cabal.dotnetgen.providers import config, factory
from cabal.dotnetgen.providers.anthropic import AnthropicProvider
from cabal.dotnetgen.providers.base import Provider, ProviderError
from cabal.dotnetgen.providers.cli_shell import CliShellProvider
from cabal.dotnetgen.providers.config import StageBinding
from cabal.dotnetgen.providers.google import GoogleProvider
from cabal.dotnetgen.providers.google import _usage_from as google_usage
from cabal.dotnetgen.providers.usage import parse_usage as anthropic_usage
from cabal.dotnetgen.providers.openai_compatible import OpenAICompatibleProvider

BINDINGS_TOML = """
[defaults]
retry_ceiling = 3
map_token_budget = 1024

[stages.route]
provider = "openai_compatible"
model = "local-model"
base_url = "http://localhost:11434/v1"

[stages.architect]
provider = "cli_shell"
model = "claude-opus-5"

[stages.architect.fallback]
provider = "anthropic"
model = "claude-sonnet-4"
api_key_env = "ANTHROPIC_API_KEY"

[stages.write]
provider = "anthropic"
model = "claude-sonnet-4"
api_key_env = "ANTHROPIC_API_KEY"
"""


@pytest.fixture
def bindings(tmp_path) -> config.Bindings:
    path = tmp_path / "bindings.toml"
    path.write_text(BINDINGS_TOML, encoding="utf-8")
    return config.load_bindings(search=(path,))


def test_each_stage_resolves_to_its_own_adapter(bindings: config.Bindings) -> None:
    assert isinstance(factory.provider_for(bindings.for_stage("route")), OpenAICompatibleProvider)
    assert isinstance(factory.provider_for(bindings.for_stage("write")), AnthropicProvider)


def test_the_subscription_stage_wraps_its_configured_fallback(bindings: config.Bindings) -> None:
    provider = factory.provider_for(bindings.for_stage("architect"))

    assert isinstance(provider, factory.FallbackProvider)
    assert isinstance(provider.primary, CliShellProvider)
    assert isinstance(provider.standby, AnthropicProvider)


def test_every_adapter_satisfies_the_shared_protocol(bindings: config.Bindings) -> None:
    """Stages depend on the protocol, so an adapter that drifts from it breaks silently."""
    for stage in ("route", "architect", "write"):
        assert isinstance(factory.provider_for(bindings.for_stage(stage)), Provider)


def test_only_the_api_key_stage_needs_a_key(bindings: config.Bindings) -> None:
    assert bindings.for_stage("write").requires_api_key is True
    assert bindings.for_stage("route").requires_api_key is False
    assert bindings.for_stage("architect").requires_api_key is False


def test_a_missing_key_is_reported_rather_than_guessed(
    bindings: config.Bindings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert bindings.for_stage("write").missing_key() is True


def test_a_key_is_read_from_the_environment_at_call_time(
    bindings: config.Bindings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never cached and never written to the bindings file - the standing secrets rule."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    assert bindings.for_stage("write").api_key() == "sk-test"
    assert "sk-test" not in BINDINGS_TOML


def test_an_api_key_adapter_refuses_to_call_without_its_key(
    bindings: config.Bindings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = AnthropicProvider(binding=bindings.for_stage("write"))

    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        provider._headers()


def test_only_the_local_stage_is_free(bindings: config.Bindings) -> None:
    """SC-008 rests on this: local costs a measured zero, hosted does not."""
    local = factory.provider_for(bindings.for_stage("route"))
    hosted = factory.provider_for(bindings.for_stage("write"))

    assert local.is_local is True
    assert hosted.is_local is False


def test_usage_is_normalised_to_one_shape_across_providers() -> None:
    """Different wire formats, one accounting shape - otherwise the ledger cannot compare them."""
    anthropic = anthropic_usage(
        {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 400}
    )
    google = google_usage(
        {"promptTokenCount": 500, "candidatesTokenCount": 20, "cachedContentTokenCount": 400}
    )

    assert anthropic.input_tokens == 500, "cache reads are added back into the total"
    assert anthropic.cached_input_tokens == google.cached_input_tokens == 400
    assert anthropic.cache_ratio == google.cache_ratio == pytest.approx(0.8)


def test_a_provider_that_cannot_report_caching_says_so_rather_than_reporting_zero() -> None:
    """An invented 0.0 would be indistinguishable from a cache that genuinely served nothing."""
    usage = google_usage({"promptTokenCount": 500, "candidatesTokenCount": 20})

    assert usage.cache_reported is False
    assert usage.cache_ratio is None
