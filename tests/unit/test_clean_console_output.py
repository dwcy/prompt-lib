"""Unit tests for clean_console_output — strips installer progress/spinner noise."""

from __future__ import annotations

from cabal.tool_catalog import clean_console_output


def test_carriage_return_progress_collapses_to_final_segment():
    raw = "Downloading\r⠋\r⠙\r⠹\rDone installing uv 0.5.1"

    assert clean_console_output(raw) == "Done installing uv 0.5.1"


def test_pure_spinner_lines_are_dropped():
    raw = "Installing\n⠋\n⠙\n⠹\nfinished"

    assert clean_console_output(raw) == "Installing\nfinished"


def test_block_progress_bar_line_is_dropped():
    raw = "fetch\n████████░░░░\ndone"

    assert clean_console_output(raw) == "fetch\ndone"


def test_ansi_escape_codes_are_stripped():
    raw = "\x1b[32mok\x1b[0m installed"

    assert clean_console_output(raw) == "ok installed"


def test_real_text_is_preserved():
    raw = "added 12 packages in 3s"

    assert clean_console_output(raw) == "added 12 packages in 3s"


def test_empty_and_none_return_empty():
    assert clean_console_output("") == ""
    assert clean_console_output(None) == ""
