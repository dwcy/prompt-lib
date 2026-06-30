# -*- coding: utf-8 -*-
"""Session cost pricing table — model prefix → USD per million tokens."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PricingEntry:
    model_prefix: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    cache_read_usd_per_mtok: float
    cache_write_usd_per_mtok: float


_BUNDLED: list[PricingEntry] = [
    PricingEntry("claude-opus-4", 15.00, 75.00, 1.50, 18.75),
    PricingEntry("claude-sonnet-4", 3.00, 15.00, 0.30, 3.75),
    PricingEntry("claude-haiku-4", 0.80, 4.00, 0.08, 1.00),
    PricingEntry("claude-fable-5", 3.00, 15.00, 0.30, 3.75),
    PricingEntry("claude-opus-3-5", 15.00, 75.00, 1.50, 18.75),
    PricingEntry("claude-sonnet-3-5", 3.00, 15.00, 0.30, 3.75),
    PricingEntry("claude-haiku-3-5", 0.80, 4.00, 0.08, 1.00),
]

_OVERRIDE_PATH = Path.home() / ".claude" / "dashboard-pricing.json"
_UNKNOWN = PricingEntry("unknown", 0.0, 0.0, 0.0, 0.0)


def load_pricing() -> list[PricingEntry]:
    """Return the effective pricing table, merging the JSON override if present."""
    entries = list(_BUNDLED)
    if _OVERRIDE_PATH.exists():
        try:
            raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
            for prefix, fields in raw.items():
                entries.insert(
                    0,
                    PricingEntry(
                        model_prefix=prefix,
                        input_usd_per_mtok=float(fields.get("input_usd_per_mtok", 0)),
                        output_usd_per_mtok=float(fields.get("output_usd_per_mtok", 0)),
                        cache_read_usd_per_mtok=float(fields.get("cache_read_usd_per_mtok", 0)),
                        cache_write_usd_per_mtok=float(fields.get("cache_write_usd_per_mtok", 0)),
                    ),
                )
        except Exception:
            pass
    return entries


def lookup(model: str, pricing: list[PricingEntry]) -> PricingEntry:
    """Return the first entry whose prefix matches the model id, or the unknown sentinel."""
    for entry in pricing:
        if model.startswith(entry.model_prefix):
            return entry
    return _UNKNOWN
