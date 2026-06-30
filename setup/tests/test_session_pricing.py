# -*- coding: utf-8 -*-
"""Tests for session_pricing — prefix match, unknown fallback, override file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal.session_pricing import PricingEntry, load_pricing, lookup


def _pricing() -> list[PricingEntry]:
    return load_pricing()


class TestLookup:
    def test_exact_prefix_match(self):
        pricing = _pricing()

        result = lookup("claude-sonnet-4-6-20251022", pricing)

        assert result.model_prefix == "claude-sonnet-4"
        assert result.input_usd_per_mtok == 3.00

    def test_opus_prefix_match(self):
        pricing = _pricing()

        result = lookup("claude-opus-4-8", pricing)

        assert result.model_prefix == "claude-opus-4"
        assert result.output_usd_per_mtok == 75.00

    def test_haiku_prefix_match(self):
        pricing = _pricing()

        result = lookup("claude-haiku-4-5-20251001", pricing)

        assert result.model_prefix == "claude-haiku-4"
        assert result.input_usd_per_mtok == 0.80

    def test_unknown_model_returns_zero_sentinel(self):
        pricing = _pricing()

        result = lookup("gpt-4o", pricing)

        assert result.model_prefix == "unknown"
        assert result.input_usd_per_mtok == 0.0
        assert result.output_usd_per_mtok == 0.0

    def test_empty_model_string_returns_unknown(self):
        pricing = _pricing()

        result = lookup("", pricing)

        assert result.model_prefix == "unknown"


class TestLoadPricing:
    def test_bundled_table_is_non_empty(self):
        pricing = load_pricing()

        assert len(pricing) > 0

    def test_override_file_prepended(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        override = tmp_path / "dashboard-pricing.json"
        override.write_text(
            json.dumps(
                {
                    "my-custom-model": {
                        "input_usd_per_mtok": 99.0,
                        "output_usd_per_mtok": 199.0,
                        "cache_read_usd_per_mtok": 9.9,
                        "cache_write_usd_per_mtok": 19.9,
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "cabal.session_pricing._OVERRIDE_PATH", override
        )

        pricing = load_pricing()

        result = lookup("my-custom-model-v1", pricing)
        assert result.input_usd_per_mtok == 99.0

    def test_malformed_override_file_falls_back_gracefully(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        override = tmp_path / "dashboard-pricing.json"
        override.write_text("not json!!!", encoding="utf-8")
        monkeypatch.setattr(
            "cabal.session_pricing._OVERRIDE_PATH", override
        )

        pricing = load_pricing()

        assert len(pricing) > 0

    def test_missing_override_file_uses_bundled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "cabal.session_pricing._OVERRIDE_PATH", tmp_path / "nonexistent.json"
        )

        pricing = load_pricing()

        assert any(e.model_prefix == "claude-sonnet-4" for e in pricing)
