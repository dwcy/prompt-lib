# -*- coding: utf-8 -*-
"""Unit tests for render_word_diff — word-level highlighting and context folding."""

from __future__ import annotations

from cabal.diff_text import render_word_diff


def _highlighted(text, needle):
    return [text.plain[s.start : s.end] for s in text.spans if needle in str(s.style)]


def test_only_changed_words_are_highlighted_not_whole_line():
    old = "A futures move can disappear after macro data."
    new = "A futures move can disappear after macro data, earnings, or bond yields."

    diff = render_word_diff(old, new)

    assert _highlighted(diff, "on dark_red") == ["data."]
    assert _highlighted(diff, "on dark_green") == ["data, earnings, or bond yields."]
    assert "A futures move can disappear after macro " not in _highlighted(
        diff, "on dark_green"
    )


def test_unchanged_runs_are_folded():
    old = "\n".join(["change me"] + [f"keep {i}" for i in range(20)])
    new = "\n".join(["CHANGED"] + [f"keep {i}" for i in range(20)])

    diff = render_word_diff(old, new)

    assert "unchanged line" in diff.plain
    assert "keep 0" in diff.plain
    assert "keep 10" not in diff.plain


def test_identical_text_reports_no_difference():
    same = "line one\nline two\n"

    diff = render_word_diff(same, same)

    assert "no textual difference" in diff.plain
