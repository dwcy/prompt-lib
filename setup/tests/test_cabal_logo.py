# -*- coding: utf-8 -*-
"""Tests for the Cabal terminal-native logo renderer."""

from __future__ import annotations

from cabal.banner import LOGO_LINES, SUBTITLE_TEXT
from cabal.widgets.logo import (
    BODY_COLOR,
    MARK_BASE_ROW_COUNT,
    MARK_COLORS,
    MARK_RENDER_ROW_COUNT,
    MARK_RENDER_WIDTH,
    MARK_ROW_HEIGHTS,
    MARK_SPRITE,
    MARK_SOURCE_WIDTH,
    render_cabal_logo,
)


def test_cabal_logo_sprite_models_elephant_features() -> None:
    sprite = "\n".join(MARK_SPRITE)

    assert "BBB" in sprite
    assert "T" not in sprite
    assert "SSSS" in sprite
    assert sprite.count("SSSS") == 5
    assert "PPBBBPPPPPPBBBP" in sprite
    assert "PPPPP.SSSS.PPPPP" in sprite
    assert MARK_SPRITE[-1] == "........PPPPP.PPPP.PPPPP........"


def test_cabal_logo_body_uses_flat_color() -> None:
    assert MARK_COLORS["P"] == BODY_COLOR
    assert MARK_COLORS["E"] == BODY_COLOR


def test_cabal_logo_default_render_size_preserves_elephant_shape() -> None:
    assert MARK_SOURCE_WIDTH == 32
    assert MARK_RENDER_WIDTH == 32
    assert MARK_RENDER_ROW_COUNT == 12

    rendered = render_cabal_logo(40, show_wordmark=False)

    assert len(rendered.plain.splitlines()) == MARK_RENDER_ROW_COUNT


def test_cabal_logo_row_heights_control_rendered_height() -> None:
    assert len(MARK_ROW_HEIGHTS) == MARK_BASE_ROW_COUNT

    row_heights = (2,) + (1,) * (MARK_BASE_ROW_COUNT - 1)
    rendered = render_cabal_logo(40, show_wordmark=False, row_heights=row_heights)

    assert len(rendered.plain.splitlines()) == sum(row_heights)


def test_cabal_logo_component_render_includes_mark_and_wordmark() -> None:
    rendered = render_cabal_logo(120)

    assert "████" in rendered.plain
    assert "██████" in rendered.plain


def test_cabal_logo_places_subtitle_under_wordmark() -> None:
    rendered = render_cabal_logo(120)
    lines = rendered.plain.splitlines()

    subtitle_idx = next(idx for idx, line in enumerate(lines) if SUBTITLE_TEXT in line)
    wordmark_end_idx = next(
        idx for idx, line in enumerate(lines) if LOGO_LINES[-1].strip() in line
    )

    assert subtitle_idx > wordmark_end_idx


def test_cabal_logo_can_hide_subtitle() -> None:
    rendered = render_cabal_logo(120, show_subtitle=False)

    assert SUBTITLE_TEXT not in rendered.plain
