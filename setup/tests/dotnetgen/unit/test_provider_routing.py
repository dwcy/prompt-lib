# -*- coding: utf-8 -*-
"""Unit tests for per-stage binding resolution and fallback (T058).

FR-027 says a stage may declare a fallback used when its primary fails. The rule that gives that
value is *which* failures trigger it: a rate limit or an unreachable host is worth a second
attempt elsewhere, while a malformed request or a missing API key will fail identically on the
standby and only doubles the latency.
"""

from __future__ import annotations

import pytest

from cabal.dotnetgen.providers import factory
from cabal.dotnetgen.providers.base import (
    CompletionRequest,
    CompletionResult,
    Message,
    ProviderError,
    ProviderStatus,
    ProviderUnavailableError,
    Usage,
)
from cabal.dotnetgen.providers.config import StageBinding

REQUEST = CompletionRequest(messages=(Message(role="user", content="hi"),), model="m")


class StubProvider:
    """Answers, or fails in a specified way, and counts calls."""

    def __init__(self, name: str, *, error: Exception | None = None, reachable: bool = True) -> None:
        self.name = name
        self._error = error
        self._reachable = reachable
        self.calls = 0
        self.is_local = False

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return CompletionResult(
            text=self.name, usage=Usage(), model="m", provider=self.name
        )

    def check(self) -> ProviderStatus:
        return ProviderStatus(self.name, "m", reachable=self._reachable, detail="" if self._reachable else "down")


def test_an_unreachable_cli_primary_does_not_surface_as_a_missing_api_key() -> None:
    """The real-world shape: a stage bound to `cli_shell` precisely so it needs no API key.

    When the CLI is not accessible the primary raises a retryable ProviderUnavailableError and
    the anthropic fallback then fails on its absent key. Reporting only the standby's message
    tells the developer to set ANTHROPIC_API_KEY -- a credential these bindings deliberately
    avoid needing -- and hides the CLI failure that actually stopped the run. Both causes must
    survive, primary first.
    """
    primary = StubProvider(
        "cli_shell", error=ProviderUnavailableError("cannot start `claude`: not found")
    )
    standby = StubProvider(
        "anthropic", error=ProviderError("ANTHROPIC_API_KEY is not set", retryable=False)
    )

    with pytest.raises(ProviderError) as excinfo:
        factory.FallbackProvider(primary, standby).complete(REQUEST)

    message = str(excinfo.value)
    assert "cannot start `claude`" in message, "the cause that actually stopped the run must survive"
    assert "ANTHROPIC_API_KEY" in message, "the fallback's own reason is still worth reporting"
    assert message.index("claude") < message.index("ANTHROPIC_API_KEY"), (
        "the primary's failure is the cause and the fallback's is the consequence; "
        "leading with the key sends the developer to fix the wrong thing"
    )


def test_a_rate_limited_primary_falls_back() -> None:
    primary = StubProvider("primary", error=ProviderError("429 rate limited", retryable=True))
    standby = StubProvider("standby")

    result = factory.FallbackProvider(primary, standby).complete(REQUEST)

    assert result.text == "standby"
    assert standby.calls == 1


def test_an_unreachable_primary_falls_back() -> None:
    primary = StubProvider("primary", error=ProviderUnavailableError("connection refused"))
    standby = StubProvider("standby")

    assert factory.FallbackProvider(primary, standby).complete(REQUEST).text == "standby"


def test_a_non_retryable_failure_does_not_fall_back() -> None:
    """A missing key or a malformed request fails the same way twice; only latency doubles."""
    primary = StubProvider("primary", error=ProviderError("API key not set", retryable=False))
    standby = StubProvider("standby")

    with pytest.raises(ProviderError, match="API key"):
        factory.FallbackProvider(primary, standby).complete(REQUEST)

    assert standby.calls == 0


def test_a_healthy_primary_is_never_second_guessed() -> None:
    primary = StubProvider("primary")
    standby = StubProvider("standby")

    factory.FallbackProvider(primary, standby).complete(REQUEST)

    assert standby.calls == 0


def test_check_reports_the_fallback_when_the_primary_is_down() -> None:
    """A stage whose standby answers is usable, and the report says why it is."""
    status = factory.FallbackProvider(
        StubProvider("primary", reachable=False), StubProvider("standby")
    ).check()

    assert status.reachable is True
    assert "primary unreachable" in status.detail


def test_check_reports_unreachable_when_both_are_down() -> None:
    status = factory.FallbackProvider(
        StubProvider("primary", reachable=False), StubProvider("standby", reachable=False)
    ).check()

    assert status.reachable is False
    assert "also unreachable" in status.detail


def test_a_binding_without_a_fallback_is_not_wrapped() -> None:
    binding = StageBinding(stage="write", provider="anthropic", model="m")

    assert not isinstance(factory.provider_for(binding), factory.FallbackProvider)


def test_a_binding_with_a_fallback_is_wrapped() -> None:
    binding = StageBinding(
        stage="write",
        provider="anthropic",
        model="m",
        fallback=StageBinding(stage="write.fallback", provider="google", model="g"),
    )

    provider = factory.provider_for(binding)

    assert isinstance(provider, factory.FallbackProvider)
    assert provider.name == "anthropic->google"


def test_an_unknown_provider_is_refused_by_name() -> None:
    binding = StageBinding(stage="write", provider="tarot", model="m")

    with pytest.raises(ProviderError, match="unknown provider"):
        factory.provider_for(binding)


def test_every_known_provider_can_be_built() -> None:
    """The registry and the builder must not drift apart."""
    for name in factory.KNOWN_PROVIDERS:
        binding = StageBinding(
            stage="write", provider=name, model="m", base_url="http://localhost:1234/v1"
        )

        assert factory.provider_for(binding).name == name
