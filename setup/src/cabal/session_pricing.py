# -*- coding: utf-8 -*-
"""Session cost pricing — model rates, request-level modifiers, and the cost formula.

Rates are expressed as one number per model: the input price per million tokens.
Every other Anthropic rate is a fixed multiple of it (see _RATIO_*), an invariant that
has held across every model generation, so a new model is one line and there are no
three extra numbers to get wrong.

Two deliberate behaviours:
  * `lookup` returns None for a model it does not know.  Callers must treat that as
    "unpriced", never as $0.00 — an unknown model and a genuinely free one mean
    opposite things, and silently pricing the unknown one at zero is how this table
    went stale without anyone noticing.
  * Prefix matching is longest-wins, so `claude-opus-4-8` ($5) is never served by a
    shorter `claude-opus-4` entry ($15).  There is intentionally no generic per-family
    catch-all: an unrecognised point release must surface as unpriced.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

# Rates that are a fixed multiple of the model's input price.
_RATIO_OUTPUT = 5.0
_RATIO_CACHE_READ = 0.1
_RATIO_CACHE_WRITE_5M = 1.25
_RATIO_CACHE_WRITE_1H = 2.0

# Request-level modifiers applied on top of the model rate.
_SPEED_MULTIPLIER = {"fast": 2.0}          # fast mode bills Opus 5/4.8 at $10/$50
_SERVICE_TIER_MULTIPLIER = {"batch": 0.5}  # Batch API is half price

#: Date the rate table below was last checked against Anthropic's published pricing.
PRICING_AS_OF = date(2026, 6, 24)


@dataclass(frozen=True)
class PricingEntry:
    """A model's rates.  Derived from `input_usd_per_mtok` unless explicitly overridden."""

    model_prefix: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float | None = None
    cache_read_usd_per_mtok: float | None = None
    cache_write_5m_usd_per_mtok: float | None = None
    cache_write_1h_usd_per_mtok: float | None = None
    # Dated rates: an intro price that lapses, or a rate change with a known start.
    effective_from: date | None = None
    effective_until: date | None = None

    @property
    def output_rate(self) -> float:
        return self._or_ratio(self.output_usd_per_mtok, _RATIO_OUTPUT)

    @property
    def cache_read_rate(self) -> float:
        return self._or_ratio(self.cache_read_usd_per_mtok, _RATIO_CACHE_READ)

    @property
    def cache_write_5m_rate(self) -> float:
        return self._or_ratio(self.cache_write_5m_usd_per_mtok, _RATIO_CACHE_WRITE_5M)

    @property
    def cache_write_1h_rate(self) -> float:
        return self._or_ratio(self.cache_write_1h_usd_per_mtok, _RATIO_CACHE_WRITE_1H)

    def _or_ratio(self, explicit: float | None, ratio: float) -> float:
        return explicit if explicit is not None else self.input_usd_per_mtok * ratio

    def covers(self, when: date | None) -> bool:
        """True when this rate was in force on `when`.

        With no date to check against, only an open-ended rate qualifies — a lapsed
        intro price must never be the fallback for a request of unknown age.
        """
        if when is None:
            return self.effective_until is None
        if self.effective_from is not None and when < self.effective_from:
            return False
        if self.effective_until is not None and when > self.effective_until:
            return False
        return True

    def scaled(self, factor: float) -> PricingEntry:
        """Return these rates multiplied by a request-level modifier (fast mode, batch)."""
        if factor == 1.0:
            return self
        return replace(
            self,
            input_usd_per_mtok=self.input_usd_per_mtok * factor,
            output_usd_per_mtok=self.output_rate * factor,
            cache_read_usd_per_mtok=self.cache_read_rate * factor,
            cache_write_5m_usd_per_mtok=self.cache_write_5m_rate * factor,
            cache_write_1h_usd_per_mtok=self.cache_write_1h_rate * factor,
        )


_BUNDLED: list[PricingEntry] = [
    # Frontier tier
    PricingEntry("claude-fable-5", 10.00),
    PricingEntry("claude-mythos-5", 10.00),
    PricingEntry("claude-mythos-preview", 10.00),
    # Opus
    PricingEntry("claude-opus-5", 5.00),
    PricingEntry("claude-opus-4-8", 5.00),
    PricingEntry("claude-opus-4-7", 5.00),
    PricingEntry("claude-opus-4-6", 5.00),
    PricingEntry("claude-opus-4-5", 5.00),
    PricingEntry("claude-opus-4-1", 15.00),
    PricingEntry("claude-opus-4-0", 15.00),
    PricingEntry("claude-opus-4-20250514", 15.00),
    PricingEntry("claude-3-opus", 15.00),
    # Sonnet.  Sonnet 5 launched on an intro rate that lapses 2026-08-31.
    PricingEntry("claude-sonnet-5", 2.00, effective_until=date(2026, 8, 31)),
    PricingEntry("claude-sonnet-5", 3.00, effective_from=date(2026, 9, 1)),
    PricingEntry("claude-sonnet-4-6", 3.00),
    PricingEntry("claude-sonnet-4-5", 3.00),
    PricingEntry("claude-sonnet-4-0", 3.00),
    PricingEntry("claude-sonnet-4-20250514", 3.00),
    PricingEntry("claude-3-7-sonnet", 3.00),
    PricingEntry("claude-3-5-sonnet", 3.00),
    # Haiku
    PricingEntry("claude-haiku-4-5", 1.00),
    PricingEntry("claude-3-5-haiku", 0.80),
    PricingEntry("claude-3-haiku", 0.25),
]

_OVERRIDE_PATH = Path.home() / ".claude" / "dashboard-pricing.json"

_OVERRIDE_RATE_FIELDS = (
    "output_usd_per_mtok",
    "cache_read_usd_per_mtok",
    "cache_write_5m_usd_per_mtok",
    "cache_write_1h_usd_per_mtok",
)


def _parse_date(raw: object) -> date | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def load_pricing() -> list[PricingEntry]:
    """Return the effective rate table, with any user override layered on top.

    Override format (~/.claude/dashboard-pricing.json) — `input_usd_per_mtok` is the only
    required field; the rest default to the standard ratios:

        {"claude-opus-6": {"input_usd_per_mtok": 6.0},
         "claude-odd-1":  {"input_usd_per_mtok": 1.0, "output_usd_per_mtok": 9.0}}
    """
    entries = list(_BUNDLED)
    if not _OVERRIDE_PATH.exists():
        return entries
    try:
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return entries
    if not isinstance(raw, dict):
        return entries
    for prefix, fields in raw.items():
        if not isinstance(fields, dict):
            continue
        try:
            base = float(fields["input_usd_per_mtok"])
        except (KeyError, TypeError, ValueError):
            continue
        overrides = {
            key: float(fields[key])
            for key in _OVERRIDE_RATE_FIELDS
            if isinstance(fields.get(key), (int, float))
        }
        # An override must beat a bundled entry of the same prefix length, so it goes first.
        entries.insert(
            0,
            PricingEntry(
                model_prefix=prefix,
                input_usd_per_mtok=base,
                effective_from=_parse_date(fields.get("effective_from")),
                effective_until=_parse_date(fields.get("effective_until")),
                **overrides,
            ),
        )
    return entries


def lookup(
    model: str,
    pricing: list[PricingEntry],
    *,
    when: date | datetime | None = None,
    speed: str | None = None,
    service_tier: str | None = None,
) -> PricingEntry | None:
    """Return the rates for `model`, or None when the table does not know it.

    Longest matching prefix wins.  `when` selects between dated rates (an intro price and
    its successor); `speed` and `service_tier` apply the request-level multipliers.
    """
    if not model:
        return None
    on = when.date() if isinstance(when, datetime) else when
    best: PricingEntry | None = None
    for entry in pricing:
        if not model.startswith(entry.model_prefix) or not entry.covers(on):
            continue
        if best is None or len(entry.model_prefix) > len(best.model_prefix):
            best = entry
    if best is None:
        return None
    factor = _SPEED_MULTIPLIER.get(speed or "", 1.0) * _SERVICE_TIER_MULTIPLIER.get(
        service_tier or "", 1.0
    )
    return best.scaled(factor)


def price_usage(
    entry: PricingEntry,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_5m_tokens: int = 0,
    cache_write_1h_tokens: int = 0,
) -> float:
    """The one place token counts turn into dollars.  Every caller goes through here."""
    return (
        input_tokens * entry.input_usd_per_mtok
        + output_tokens * entry.output_rate
        + cache_read_tokens * entry.cache_read_rate
        + cache_write_5m_tokens * entry.cache_write_5m_rate
        + cache_write_1h_tokens * entry.cache_write_1h_rate
    ) / 1_000_000
