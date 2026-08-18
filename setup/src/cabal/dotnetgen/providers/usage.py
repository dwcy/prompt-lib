# -*- coding: utf-8 -*-
"""Normalise provider-reported token usage into `base.Usage`.

Shared by every adapter because the field names differ per provider while the accounting must
not. Two behaviours matter here and both protect SC-005 and SC-010:

1. **Absence is reported, not zeroed.** When a payload carries no cache field, `cache_reported`
   is False so a zero can never masquerade as a measurement.
2. **The two conventions count differently.** Anthropic reports `input_tokens` *excluding* cache
   reads and writes, so the total is additive. OpenAI's `prompt_tokens` *includes* its
   `cached_tokens`, so adding them would double-count. The convention is detected, not assumed.
"""

from __future__ import annotations

from typing import Any, Final

from cabal.dotnetgen.providers.base import Usage

_ANTHROPIC_INPUT: Final[str] = "input_tokens"
_ANTHROPIC_OUTPUT: Final[str] = "output_tokens"
_ANTHROPIC_CACHE_READ: Final[str] = "cache_read_input_tokens"
_ANTHROPIC_CACHE_WRITE: Final[str] = "cache_creation_input_tokens"

_OPENAI_INPUT: Final[str] = "prompt_tokens"
_OPENAI_OUTPUT: Final[str] = "completion_tokens"
_OPENAI_CACHE_READ: Final[str] = "cached_tokens"
_OPENAI_CACHE_DETAILS: Final[str] = "prompt_tokens_details"


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _get_int(payload: dict, key: str) -> int | None:
    return _as_int(payload.get(key))


def _openai_cached(payload: dict) -> int | None:
    """OpenAI nests cache hits under `prompt_tokens_details.cached_tokens`; some proxies flatten it."""
    details = payload.get(_OPENAI_CACHE_DETAILS)
    if isinstance(details, dict):
        nested = _as_int(details.get(_OPENAI_CACHE_READ))
        if nested is not None:
            return nested
    return _get_int(payload, _OPENAI_CACHE_READ)


def _parse_anthropic(payload: dict) -> Usage:
    """`input_tokens` excludes cache traffic, so the true input total is additive."""
    uncached = _get_int(payload, _ANTHROPIC_INPUT) or 0
    cache_read = _get_int(payload, _ANTHROPIC_CACHE_READ)
    cache_write = _get_int(payload, _ANTHROPIC_CACHE_WRITE)
    reported = cache_read is not None or cache_write is not None

    return Usage(
        input_tokens=uncached + (cache_read or 0) + (cache_write or 0),
        output_tokens=_get_int(payload, _ANTHROPIC_OUTPUT) or 0,
        cached_input_tokens=cache_read or 0,
        cache_reported=reported,
    )


def _parse_openai(payload: dict) -> Usage:
    """`prompt_tokens` already includes `cached_tokens`, so the total is taken as-is."""
    cache_read = _openai_cached(payload)

    return Usage(
        input_tokens=_get_int(payload, _OPENAI_INPUT) or 0,
        output_tokens=_get_int(payload, _OPENAI_OUTPUT) or 0,
        cached_input_tokens=cache_read or 0,
        cache_reported=cache_read is not None,
    )


def parse_usage(payload: Any) -> Usage:
    """Build a `Usage` from any provider's usage object, detecting which convention it uses."""
    if not isinstance(payload, dict):
        return Usage(cache_reported=False)

    if _ANTHROPIC_INPUT in payload or _ANTHROPIC_CACHE_READ in payload:
        return _parse_anthropic(payload)
    if _OPENAI_INPUT in payload or _OPENAI_CACHE_DETAILS in payload:
        return _parse_openai(payload)

    return Usage(cache_reported=False)
