# -*- coding: utf-8 -*-
"""Build a concrete provider from a stage binding.

Stages depend on the `Provider` protocol, never on an adapter, so this is the only place that
knows which module serves which provider name.

`FallbackProvider` implements FR-027: when a binding declares a fallback, a *retryable* failure on
the primary - a rate limit, a timeout, a 5xx, an unreachable host - is retried once on the
fallback. A non-retryable failure is not, because a malformed request or a missing API key will
fail identically on the second provider and trying twice only doubles the latency.
"""

from __future__ import annotations

from typing import Final

from dataclasses import dataclass

from cabal.dotnetgen.providers.anthropic import PROVIDER_NAME as ANTHROPIC
from cabal.dotnetgen.providers.anthropic import AnthropicProvider
from cabal.dotnetgen.providers.base import (
    CompletionRequest,
    CompletionResult,
    Provider,
    ProviderError,
    ProviderStatus,
)
from cabal.dotnetgen.providers.cli_shell import PROVIDER_NAME as CLI_SHELL
from cabal.dotnetgen.providers.cli_shell import CliShellProvider
from cabal.dotnetgen.providers.config import Bindings, StageBinding
from cabal.dotnetgen.providers.google import PROVIDER_NAME as GOOGLE
from cabal.dotnetgen.providers.google import GoogleProvider
from cabal.dotnetgen.providers.openai_compatible import PROVIDER_NAME as OPENAI_COMPATIBLE
from cabal.dotnetgen.providers.openai_compatible import OpenAICompatibleProvider

KNOWN_PROVIDERS: Final[frozenset[str]] = frozenset(
    {CLI_SHELL, OPENAI_COMPATIBLE, ANTHROPIC, GOOGLE}
)


def _adapter_for(binding: StageBinding) -> Provider:
    if binding.provider == CLI_SHELL:
        return CliShellProvider(binding=binding)
    if binding.provider == OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(binding=binding)
    if binding.provider == ANTHROPIC:
        return AnthropicProvider(binding=binding)
    if binding.provider == GOOGLE:
        return GoogleProvider(binding=binding)
    raise ProviderError(
        f"unknown provider {binding.provider!r}; expected one of {sorted(KNOWN_PROVIDERS)}"
    )


@dataclass(frozen=True)
class FallbackProvider:
    """Primary provider with a standby, used when the primary fails in a way a retry could fix."""

    primary: Provider
    standby: Provider

    @property
    def name(self) -> str:
        return f"{self.primary.name}->{self.standby.name}"

    @property
    def is_local(self) -> bool:
        return bool(getattr(self.primary, "is_local", False))

    def complete(self, request: CompletionRequest) -> CompletionResult:
        try:
            return self.primary.complete(request)
        except ProviderError as exc:
            if not exc.retryable:
                # A bad request or a missing key fails the same way twice; only the latency doubles.
                raise
            try:
                return self.standby.complete(request)
            except ProviderError as standby_exc:
                # Report BOTH causes. The standby's own message alone is actively misleading:
                # when a stage is bound to `cli_shell` precisely so it needs no API key, an
                # unreachable CLI surfaces here as "ANTHROPIC_API_KEY is not set", pointing the
                # developer at a credential their bindings deliberately avoid instead of at the
                # CLI that actually failed. The fallback's missing key is a consequence, not the
                # cause, so the primary's reason has to survive.
                raise ProviderError(
                    f"{self.primary.name} unavailable ({exc}); "
                    f"fallback {self.standby.name} also unusable ({standby_exc})",
                    retryable=standby_exc.retryable,
                ) from standby_exc

    def check(self) -> ProviderStatus:
        primary = self.primary.check()
        if primary.reachable:
            return primary
        standby = self.standby.check()
        return ProviderStatus(
            provider=self.name,
            model=standby.model,
            reachable=standby.reachable,
            detail=f"primary unreachable ({primary.detail}); fallback "
            + ("reachable" if standby.reachable else f"also unreachable ({standby.detail})"),
        )


def provider_for(binding: StageBinding) -> Provider:
    """Instantiate the adapter a binding names, wrapping it when a fallback is configured."""
    primary = _adapter_for(binding)
    if binding.fallback is None:
        return primary
    return FallbackProvider(primary=primary, standby=_adapter_for(binding.fallback))


def providers_for_stages(bindings: Bindings) -> dict[str, Provider]:
    """Instantiate every model-bound stage's provider."""
    return {stage: provider_for(binding) for stage, binding in bindings.stages.items()}
