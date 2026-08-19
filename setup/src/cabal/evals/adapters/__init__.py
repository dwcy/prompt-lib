# -*- coding: utf-8 -*-
"""Agent adapter registry: name -> factory, selected by eval.config.toml's `adapter` value.

Drop-in contract for future adapters (codex, gemini, ...): implement the `AgentAdapter` protocol
from `cabal.evals.adapters.base` (a `name` attribute plus `check()` / `capabilities()` / `run()`
— no base class required), then call `register(name, factory)` at import time in your module and
import that module here. Fields your CLI cannot report are declared False in `capabilities()` so
metrics records null, never a fabricated zero.
"""

from __future__ import annotations

from collections.abc import Callable

from cabal.evals.adapters.base import AgentAdapter


class UnknownAdapterError(ValueError):
    """No adapter is registered under the requested name."""


_REGISTRY: dict[str, Callable[[], AgentAdapter]] = {}


def register(name: str, factory: Callable[[], AgentAdapter]) -> None:
    """Register an adapter factory under its eval.config.toml `adapter` name."""
    _REGISTRY[name] = factory


def registered_names() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def get_adapter(name: str) -> AgentAdapter:
    """Instantiate the adapter registered under `name`; unknown names are a validate-time error."""
    factory = _REGISTRY.get(name)
    if factory is None:
        known = ", ".join(registered_names()) or "(none registered)"
        raise UnknownAdapterError(f"unknown adapter {name!r}; registered adapters: {known}")
    return factory()
