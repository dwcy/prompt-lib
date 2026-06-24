# -*- coding: utf-8 -*-
"""Cabal terminal-native logo widget."""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Group
from rich.text import Text
from textual.widgets import Static

from cabal.banner import (
    LOGO_GRADIENT,
    LOGO_LINES,
    LOGO_MAX_WIDTH,
    SUBTITLE_STYLE,
    SUBTITLE_TEXT,
)

BODY_COLOR = "#FF4AA0"
EAR_COLOR = "#FF4AA0"
TRUNK_DETAIL_COLOR = "#E7438A"
EYE_COLOR = "#000000"
MARK_SPRITE = [
    "........PPPPPPPPPPPPPPPP........",
    ".......PPPPPPPPPPPPPPPPPP.......",
    "......PPPPPPPPPPPPPPPPPPPP......",
    "......PPPPPPPPPPPPPPPPPPPP......",
    "......PPPPPPPPPPPPPPPPPPPP......",
    ".EEEEEEEPPPPPPPPPPPPPPPPEEEEEEE.",
    ".EEEEEEEPPPPPPPPPPPPPPPPEEEEEEE.",
    ".EEEEEEEPPBBBPPPPPPBBBPPEEEEEEE.",
    ".EEEEEEEPPBBBPPPPPPBBBPPEEEEEEE.",
    ".EEEEEEEPPBBBPPPPPPBBBPPEEEEEEE.",
    ".EEEEEEEPPPPPPPPPPPPPPPPEEEEEEE.",
    ".EEEEEEEPPPPPPPPPPPPPPPPEEEEEEE.",
    ".EEEEEEEPPPPPPSSSSPPPPPPEEEEEEE.",
    "......PPPPPPPPPPPPPPPPPPPP......",
    "......PPPPPPPPSSSSPPPPPPPP......",
    "......PPPPPPPPPPPPPPPPPPPP......",
    "......PPPPPPPPSSSSPPPPPPPP......",
    "........PPPPP.PPPP.PPPPP........",
    "........PPPPP.SSSS.PPPPP........",
    "........PPPPP.PPPP.PPPPP........",
    "........PPPPP.PPPP.PPPPP........",
    "........PPPPP.SSSS.PPPPP........",
    "........PPPPP.PPPP.PPPPP........",
    "........PPPPP.PPPP.PPPPP........",
]
MARK_COLORS = {
    "P": BODY_COLOR,
    "E": EAR_COLOR,
    "S": TRUNK_DETAIL_COLOR,
    "B": EYE_COLOR,
}
MARK_SOURCE_WIDTH = max(len(line) for line in MARK_SPRITE)
MARK_RENDER_WIDTH = 32
MARK_RENDER_ROW_COUNT = 12
MARK_RENDER_PIXEL_HEIGHT = MARK_RENDER_ROW_COUNT * 2
MARK_MAX_WIDTH = MARK_RENDER_WIDTH
MARK_BASE_ROW_COUNT = MARK_RENDER_ROW_COUNT
# Terminal fonts own actual line height; these repeat rendered rows instead.
MARK_ROW_HEIGHTS = (1,) * MARK_BASE_ROW_COUNT


def _wordmark_rows() -> list[Text]:
    rows: list[Text] = []
    for idx, line in enumerate(LOGO_LINES):
        color_idx = min(
            (idx * len(LOGO_GRADIENT)) // max(1, len(LOGO_LINES) - 1),
            len(LOGO_GRADIENT) - 1,
        )
        rows.append(Text(line.rstrip(), style=f"bold {LOGO_GRADIENT[color_idx]}"))
    return rows


def _subtitle_row() -> Text:
    return Text(SUBTITLE_TEXT, style=SUBTITLE_STYLE)


def _append_centered(target: Text, source: Text, width: int) -> None:
    pad = max(0, (width - len(source.plain)) // 2)
    if pad:
        target.append(" " * pad)
    target.append_text(source)


def _pixel_color(pixel: str) -> str | None:
    if pixel == ".":
        return None
    return MARK_COLORS[pixel]


def _append_pixel_pair(row: Text, top: str, bottom: str) -> None:
    top_color = _pixel_color(top)
    bottom_color = _pixel_color(bottom)

    if top_color and bottom_color:
        if top_color == bottom_color:
            row.append("█", style=top_color)
        else:
            row.append("▀", style=f"{top_color} on {bottom_color}")
    elif top_color:
        row.append("▀", style=top_color)
    elif bottom_color:
        row.append("▄", style=bottom_color)
    else:
        row.append(" ")


def _resolved_row_heights(
    row_count: int,
    row_heights: Sequence[int] | None,
) -> Sequence[int]:
    heights = row_heights if row_heights is not None else (1,) * row_count
    if len(heights) != row_count:
        raise ValueError(f"expected {row_count} row heights, got {len(heights)}")
    if any(height < 0 for height in heights):
        raise ValueError("row heights must be zero or greater")
    return heights


def _scaled_sprite(width: int, pixel_height: int) -> list[str]:
    source_height = len(MARK_SPRITE)
    rows: list[str] = []
    for y in range(pixel_height):
        source_y = min(source_height - 1, int((y + 0.5) * source_height / pixel_height))
        chars: list[str] = []
        for x in range(width):
            source_x = min(MARK_SOURCE_WIDTH - 1, int((x + 0.5) * MARK_SOURCE_WIDTH / width))
            chars.append(MARK_SPRITE[source_y][source_x])
        rows.append("".join(chars))
    return rows


def _mark_rows(
    row_heights: Sequence[int] | None = None,
    *,
    mark_width: int = MARK_RENDER_WIDTH,
    mark_rows: int = MARK_RENDER_ROW_COUNT,
) -> list[Text]:
    if mark_width <= 0:
        raise ValueError("mark width must be greater than zero")
    if mark_rows <= 0:
        raise ValueError("mark rows must be greater than zero")

    base_rows: list[Text] = []
    scaled_sprite = _scaled_sprite(mark_width, mark_rows * 2)
    empty = "." * mark_width
    for top_idx in range(0, len(scaled_sprite), 2):
        top = scaled_sprite[top_idx]
        bottom = scaled_sprite[top_idx + 1] if top_idx + 1 < len(scaled_sprite) else empty
        row = Text()
        for top_cell, bottom_cell in zip(top, bottom):
            _append_pixel_pair(row, top_cell, bottom_cell)
        base_rows.append(row)

    rows: list[Text] = []
    heights = _resolved_row_heights(len(base_rows), row_heights)
    for row, height in zip(base_rows, heights, strict=True):
        for _ in range(height):
            rows.append(row.copy())
    return rows


def render_cabal_logo(
    target_width: int | None = None,
    *,
    show_wordmark: bool = True,
    show_subtitle: bool = True,
    row_heights: Sequence[int] | None = None,
    mark_width: int = MARK_RENDER_WIDTH,
    mark_rows: int = MARK_RENDER_ROW_COUNT,
) -> Text:
    """Render a Cabal header designed for terminal cells."""
    width = max(24, target_width or 80)
    mark = _mark_rows(row_heights, mark_width=mark_width, mark_rows=mark_rows)

    if not show_wordmark:
        output = Text()
        for idx, row in enumerate(mark):
            if idx:
                output.append("\n")
            _append_centered(output, row, width)
        return output

    wordmark = _wordmark_rows()
    word_block = wordmark + ([_subtitle_row()] if show_subtitle else [])
    word_block_width = max(len(row.plain) for row in word_block)

    if width < mark_width + word_block_width + 2:
        output = Text()
        block_width = max(mark_width, word_block_width, width)
        for idx, row in enumerate(mark + [Text("")] + word_block):
            if idx:
                output.append("\n")
            _append_centered(output, row, block_width)
        return output

    total_rows = max(len(mark), len(word_block))
    mark_start = (total_rows - len(mark)) // 2
    word_start = (total_rows - len(word_block)) // 2
    output = Text()

    for idx in range(total_rows):
        if idx:
            output.append("\n")

        if mark_start <= idx < mark_start + len(mark):
            output.append_text(mark[idx - mark_start])
        else:
            output.append(" " * mark_width)

        output.append("  ")

        if word_start <= idx < word_start + len(word_block):
            output.append_text(word_block[idx - word_start])

    return output


class CabalLogo(Static):
    """Static widget that renders Cabal's terminal-native brand header."""

    def __init__(
        self,
        *args,
        show_wordmark: bool = True,
        show_subtitle: bool = True,
        row_heights: Sequence[int] | None = None,
        mark_width: int = MARK_RENDER_WIDTH,
        mark_rows: int = MARK_RENDER_ROW_COUNT,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.show_wordmark = show_wordmark
        self.show_subtitle = show_subtitle
        self.row_heights = row_heights
        self.mark_width = mark_width
        self.mark_rows = mark_rows

    def on_mount(self) -> None:
        self._refresh()

    def on_resize(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        logo = render_cabal_logo(
            self.size.width or None,
            show_wordmark=self.show_wordmark,
            show_subtitle=self.show_subtitle,
            row_heights=self.row_heights,
            mark_width=self.mark_width,
            mark_rows=self.mark_rows,
        )
        self.update(Group(logo))
