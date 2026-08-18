# -*- coding: utf-8 -*-
"""Build a concrete provider from a stage binding.

Stages depend on the `Provider` protocol, never on an adapter, so this is the only place that
knows which module serves which provider name. Fallback selection on failure arrives with T053.
"""

from __future__ import annotations

from typing import Final

from cabal.dotnetgen.providers.base import Provider, ProviderError
from cabal.dotnetgen.providers.cli_shell import PROVIDER_NAME as CLI_SHELL
from cabal.dotnetgen.providers.cli_shell import CliShellProvider
from cabal.dotnetgen.providers.config import Bindings, StageBinding
from cabal.dotnetgen.providers.openai_compatible import PROVIDER_NAME as OPENAI_COMPATIBLE
from cabal.dotnetgen.providers.openai_compatible import OpenAICompatibleProvider

# Adapters that exist today. `anthropic` and `google` join in T053/T054.
KNOWN_PROVIDERS: Final[frozenset[str]] = frozenset({CLI_SHELL, OPENAI_COMPATIBLE})
_PENDING_PROVIDERS: Final[dict[str, str]] = {"anthropic": "T053", "google": "T054"}


def provider_for(binding: StageBinding) -> Provider:
    """Instantiate the adapter a binding names."""
    if binding.provider == CLI_SHELL:
        return CliShellProvider(binding=binding)
    if binding.provider == OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(binding=binding)

    pending = _PENDING_PROVIDERS.get(binding.provider)
    if pending is not None:
        raise ProviderError(
            f"provider {binding.provider!r} (stage {binding.stage!r}) is implemented in {pending}"
        )
    raise ProviderError(
        f"unknown provider {binding.provider!r}; expected one of {sorted(KNOWN_PROVIDERS)}"
    )


def providers_for_stages(bindings: Bindings) -> dict[str, Provider]:
    """Instantiate every model-bound stage's provider."""
    return {stage: provider_for(binding) for stage, binding in bindings.stages.items()}
