# -*- coding: utf-8 -*-
"""Honeycomb banner rendering + the HexBanner widget."""

from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal
from textual.widgets import Static

GRID_HEIGHT = 10  # tall enough to wrap the 6-line logo with 2 hex rows above/below
_TILE_WIDTH = 6  # each hex tile is 6 cells wide

LOGO_LINES = [
    " ██████╗ █████╗ ██████╗  █████╗ ██╗",
    "██╔════╝██╔══██╗██╔══██╗██╔══██╗██║",
    "██║     ███████║██████╔╝███████║██║",
    "██║     ██╔══██║██╔══██╗██╔══██║██║",
    "╚██████╗██║  ██║██████╔╝██║  ██║███████╗",
    " ╚═════╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝",
]
LOGO_MAX_WIDTH = max(len(l) for l in LOGO_LINES)
LOGO_GUTTER = 1  # cells of clear space between hex and any logo char on the same row
# Enough tiles to wrap the logo with a 1-tile margin on each side.
_MIN_TILES = (LOGO_MAX_WIDTH + 2 * (LOGO_GUTTER + _TILE_WIDTH)) // _TILE_WIDTH + 1

LOGO_GRADIENT = ["#FFB6C1", "#FF85B3", "#FF55A5", "#FF2897", "#FF0080", "#CC006B"]
MASCOT_GRADIENT = ["#CC006B", "#FF2897", "#FF85B3", "#FFB6C1"]
SUBTITLE_TEXT = "« Cabal helps you manage your agentic development setup in one place. »"
SUBTITLE_STYLE = "italic bold #FF55A5"


def render_banner(target_width: int | None = None, subtitle: bool = True) -> Text:
    """Honeycomb grid hugging a centered CABAL logo, sized to `target_width` cells."""
    if target_width is None or target_width <= 0:
        target_width = (
            _MIN_TILES + 4
        ) * _TILE_WIDTH  # sensible default outside Textual
    tiles = max(_MIN_TILES, target_width // _TILE_WIDTH)
    grid_row_a = "  \\__/" * tiles
    grid_row_b = "__/" + "  \\__/" * (tiles - 1) + "  \\"
    grid_width = len(grid_row_a)

    txt = Text()
    logo_start = (GRID_HEIGHT - len(LOGO_LINES)) // 2
    left_pad = (grid_width - LOGO_MAX_WIDTH) // 2

    for i in range(GRID_HEIGHT):
        base = (grid_row_a if i % 2 == 0 else grid_row_b).ljust(grid_width)

        mascot_idx = min(
            (i * len(MASCOT_GRADIENT)) // max(1, GRID_HEIGHT - 1),
            len(MASCOT_GRADIENT) - 1,
        )
        mascot_style = f"bold {MASCOT_GRADIENT[mascot_idx]}"

        li = i - logo_start
        if 0 <= li < len(LOGO_LINES):
            raw = LOGO_LINES[li]
            stripped = raw.rstrip()
            if not stripped:
                txt.append(base + "\n", style=mascot_style)
                continue
            left_char = len(raw) - len(raw.lstrip())
            right_char = len(stripped)

            logo_color_idx = min(
                (li * len(LOGO_GRADIENT)) // max(1, len(LOGO_LINES) - 1),
                len(LOGO_GRADIENT) - 1,
            )
            logo_style = f"bold {LOGO_GRADIENT[logo_color_idx]}"

            cz_start = max(0, left_pad + left_char - LOGO_GUTTER)
            cz_end = min(grid_width, left_pad + right_char + LOGO_GUTTER)
            gutter_left = (left_pad + left_char) - cz_start
            gutter_right = cz_end - (left_pad + right_char)

            txt.append(base[:cz_start], style=mascot_style)
            txt.append(" " * gutter_left, style=mascot_style)
            txt.append(raw[left_char:right_char], style=logo_style)
            txt.append(" " * gutter_right, style=mascot_style)
            txt.append(base[cz_end:] + "\n", style=mascot_style)
        else:
            txt.append(base + "\n", style=mascot_style)

    if subtitle:
        txt.append(f"\n{SUBTITLE_TEXT}", style=SUBTITLE_STYLE)
    return txt


class HexBanner(Static):
    """Static that re-renders the honeycomb banner whenever its width changes."""

    def __init__(self, *args, show_subtitle: bool = True, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.show_subtitle = show_subtitle

    def on_mount(self) -> None:
        self._refresh()

    def on_resize(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self.update(render_banner(self.size.width or None, subtitle=self.show_subtitle))


def subtitle_bar() -> Horizontal:
    """Subtitle line shared by the home and start (project-gate) views."""
    return Horizontal(
        Static(SUBTITLE_TEXT, id="subtitle"),
        id="banner-row",
    )
