# -*- coding: utf-8 -*-
"""Tests for session_pricing — longest-prefix match, unpriced models, dated rates,
request modifiers, derived ratios, and the override file."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from cabal.session_pricing import (
    PRICING_AS_OF,
    PricingEntry,
    load_pricing,
    lookup,
    price_usage,
)

# Any date inside the Sonnet 5 intro window, so dated-rate tests do not drift with the clock.
INTRO = date(2026, 8, 1)
POST_INTRO = date(2026, 9, 1)


def _pricing() -> list[PricingEntry]:
    return load_pricing()


class TestLookup:
    def test_dated_model_id_matches_its_prefix(self):
        result = lookup("claude-haiku-4-5-20251001", _pricing())

        assert result is not None
        assert result.model_prefix == "claude-haiku-4-5"
        assert result.input_usd_per_mtok == 1.00

    def test_longest_prefix_wins_over_shorter_family_entry(self):
        """The regression that started this: `claude-opus-4-8` is $5, not the $15 of Opus 4.1."""
        pricing = _pricing()

        newer = lookup("claude-opus-4-8", pricing)
        older = lookup("claude-opus-4-1", pricing)

        assert newer is not None and older is not None
        assert newer.model_prefix == "claude-opus-4-8"
        assert newer.input_usd_per_mtok == 5.00
        assert older.input_usd_per_mtok == 15.00

    @pytest.mark.parametrize(
        ("model", "expected_input"),
        [
            ("claude-opus-5", 5.00),
            ("claude-sonnet-5", 2.00),  # intro rate on INTRO
            ("claude-fable-5", 10.00),
            ("claude-haiku-4-5", 1.00),
        ],
    )
    def test_current_models_are_all_priced(self, model: str, expected_input: float):
        """Guards the actual failure mode: a shipped model missing from the table."""
        result = lookup(model, _pricing(), when=INTRO)

        assert result is not None, f"{model} is unpriced"
        assert result.input_usd_per_mtok == expected_input

    def test_unknown_model_is_unpriced_not_free(self):
        assert lookup("gpt-4o", _pricing()) is None
        assert lookup("claude-opus-9", _pricing()) is None
        assert lookup("<synthetic>", _pricing()) is None

    def test_empty_model_string_is_unpriced(self):
        assert lookup("", _pricing()) is None


class TestDerivedRates:
    def test_rates_follow_the_standard_ratios(self):
        entry = lookup("claude-opus-5", _pricing())

        assert entry is not None
        assert entry.input_usd_per_mtok == 5.00
        assert entry.output_rate == 25.00
        assert entry.cache_read_rate == 0.50
        assert entry.cache_write_5m_rate == 6.25
        assert entry.cache_write_1h_rate == 10.00

    def test_explicit_override_beats_the_ratio(self):
        entry = PricingEntry("x", 1.0, output_usd_per_mtok=9.0)

        assert entry.output_rate == 9.0
        assert entry.cache_read_rate == 0.1  # still derived


class TestDatedRates:
    def test_intro_rate_applies_inside_its_window(self):
        entry = lookup("claude-sonnet-5", _pricing(), when=INTRO)

        assert entry is not None
        assert entry.input_usd_per_mtok == 2.00

    def test_standard_rate_applies_after_the_intro_lapses(self):
        entry = lookup("claude-sonnet-5", _pricing(), when=POST_INTRO)

        assert entry is not None
        assert entry.input_usd_per_mtok == 3.00

    def test_undated_lookup_never_picks_a_lapsed_intro_rate(self):
        """With no request date, only an open-ended rate qualifies — the safe default."""
        entry = lookup("claude-sonnet-5", _pricing())

        assert entry is not None
        assert entry.input_usd_per_mtok == 3.00


class TestRequestModifiers:
    def test_fast_mode_doubles_every_rate(self):
        entry = lookup("claude-opus-5", _pricing(), speed="fast")

        assert entry is not None
        assert entry.input_usd_per_mtok == 10.00
        assert entry.output_rate == 50.00
        assert entry.cache_read_rate == 1.00

    def test_standard_speed_is_unchanged(self):
        assert lookup("claude-opus-5", _pricing(), speed="standard") == lookup(
            "claude-opus-5", _pricing()
        )

    def test_batch_tier_is_half_price(self):
        entry = lookup("claude-opus-5", _pricing(), service_tier="batch")

        assert entry is not None
        assert entry.input_usd_per_mtok == 2.50


class TestPriceUsage:
    def test_each_token_class_bills_at_its_own_rate(self):
        entry = PricingEntry("x", 10.0)  # out 50, read 1.0, w5m 12.5, w1h 20

        cost = price_usage(
            entry,
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_read_tokens=1_000_000,
            cache_write_5m_tokens=1_000_000,
            cache_write_1h_tokens=1_000_000,
        )

        assert cost == pytest.approx(10.0 + 50.0 + 1.0 + 12.5 + 20.0)

    def test_one_hour_cache_writes_cost_more_than_five_minute_ones(self):
        entry = PricingEntry("x", 10.0)

        assert price_usage(entry, cache_write_1h_tokens=1_000_000) > price_usage(
            entry, cache_write_5m_tokens=1_000_000
        )


class TestLoadPricing:
    def test_bundled_table_is_non_empty(self):
        assert len(load_pricing()) > 0

    def test_pricing_as_of_is_a_real_date(self):
        assert PRICING_AS_OF.year >= 2026

    def test_override_wins_over_a_bundled_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        override = tmp_path / "dashboard-pricing.json"
        override.write_text(
            json.dumps({"claude-opus-5": {"input_usd_per_mtok": 99.0}}), encoding="utf-8"
        )
        monkeypatch.setattr("cabal.session_pricing._OVERRIDE_PATH", override)

        result = lookup("claude-opus-5", load_pricing())

        assert result is not None
        assert result.input_usd_per_mtok == 99.0
        assert result.output_rate == 495.0  # ratio still derived from the override

    def test_override_can_price_a_model_the_table_does_not_know(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        override = tmp_path / "dashboard-pricing.json"
        override.write_text(
            json.dumps({"claude-opus-9": {"input_usd_per_mtok": 7.0}}), encoding="utf-8"
        )
        monkeypatch.setattr("cabal.session_pricing._OVERRIDE_PATH", override)

        result = lookup("claude-opus-9-20270101", load_pricing())

        assert result is not None
        assert result.input_usd_per_mtok == 7.0

    def test_override_entry_without_a_base_rate_is_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        override = tmp_path / "dashboard-pricing.json"
        override.write_text(json.dumps({"claude-opus-5": {"note": "oops"}}), encoding="utf-8")
        monkeypatch.setattr("cabal.session_pricing._OVERRIDE_PATH", override)

        result = lookup("claude-opus-5", load_pricing())

        assert result is not None
        assert result.input_usd_per_mtok == 5.00  # bundled rate survives

    def test_malformed_override_file_falls_back_gracefully(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        override = tmp_path / "dashboard-pricing.json"
        override.write_text("not json!!!", encoding="utf-8")
        monkeypatch.setattr("cabal.session_pricing._OVERRIDE_PATH", override)

        assert len(load_pricing()) > 0

    def test_missing_override_file_uses_bundled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            "cabal.session_pricing._OVERRIDE_PATH", tmp_path / "nonexistent.json"
        )

        assert any(e.model_prefix == "claude-opus-5" for e in load_pricing())
