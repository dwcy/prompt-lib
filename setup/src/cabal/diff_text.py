# -*- coding: utf-8 -*-
"""Word-level diff renderer — builds a coloured Rich Text from two strings.

Line-based diffs repaint a whole line when one word changes. This aligns lines,
then within each changed line pair highlights only the words that actually
differ, and folds long runs of unchanged lines down to a few lines of context.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from rich.text import Text

_TOKEN = re.compile(r"\S+|\s+")
_CONTEXT = 3  # unchanged lines kept on each side of a change

_DEL = "red"  # unchanged words inside a removed line
_DEL_HL = "bold white on dark_red"  # the words that were removed
_INS = "green"  # unchanged words inside an added line
_INS_HL = "bold white on dark_green"  # the words that were added
_CTX = "dim"  # unchanged context lines
_GUTTER = "dim cyan"  # the - / + / space sign column
_FOLD = "dim italic"


def render_word_diff(old: str, new: str) -> Text:
    if old == new:
        return Text("(no textual difference)", style="dim")
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    out = Text()
    out.append("- removed (deployed)   ", style=_DEL)
    out.append("+ added (repo)\n\n", style=_INS)
    blocks = SequenceMatcher(a=old_lines, b=new_lines, autojunk=False).get_opcodes()
    last = len(blocks) - 1
    for idx, (tag, i1, i2, j1, j2) in enumerate(blocks):
        if tag == "equal":
            _emit_context(out, old_lines[i1:i2], idx == 0, idx == last)
        elif tag == "delete":
            for ln in old_lines[i1:i2]:
                _emit_line(out, "-", ln, _DEL)
        elif tag == "insert":
            for ln in new_lines[j1:j2]:
                _emit_line(out, "+", ln, _INS)
        else:  # replace
            _emit_replace(out, old_lines[i1:i2], new_lines[j1:j2])
    return out


def _emit_line(out: Text, sign: str, text: str, style: str) -> None:
    out.append(f"{sign} ", style=_GUTTER)
    out.append(text + "\n", style=style)


def _emit_fold(out: Text, hidden: int) -> None:
    if hidden > 0:
        out.append(
            f"  ⋯ {hidden} unchanged line{'s' if hidden != 1 else ''}\n", style=_FOLD
        )


def _emit_context(out: Text, lines: list[str], first: bool, last: bool) -> None:
    n = len(lines)
    if n <= 2 * _CONTEXT:
        for ln in lines:
            _emit_line(out, " ", ln, _CTX)
        return
    if first:
        _emit_fold(out, n - _CONTEXT)
        for ln in lines[-_CONTEXT:]:
            _emit_line(out, " ", ln, _CTX)
    elif last:
        for ln in lines[:_CONTEXT]:
            _emit_line(out, " ", ln, _CTX)
        _emit_fold(out, n - _CONTEXT)
    else:
        for ln in lines[:_CONTEXT]:
            _emit_line(out, " ", ln, _CTX)
        _emit_fold(out, n - 2 * _CONTEXT)
        for ln in lines[-_CONTEXT:]:
            _emit_line(out, " ", ln, _CTX)


def _emit_replace(out: Text, old_block: list[str], new_block: list[str]) -> None:
    sm = SequenceMatcher(a=old_block, b=new_block, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for ln in old_block[i1:i2]:
                _emit_line(out, " ", ln, _CTX)
        elif tag == "delete":
            for ln in old_block[i1:i2]:
                _emit_line(out, "-", ln, _DEL)
        elif tag == "insert":
            for ln in new_block[j1:j2]:
                _emit_line(out, "+", ln, _INS)
        else:  # replace — pair lines by position, word-diff each pair
            o, n = old_block[i1:i2], new_block[j1:j2]
            pairs = min(len(o), len(n))
            for k in range(pairs):
                _emit_word_pair(out, o[k], n[k])
            for ln in o[pairs:]:
                _emit_line(out, "-", ln, _DEL)
            for ln in n[pairs:]:
                _emit_line(out, "+", ln, _INS)


def _emit_word_pair(out: Text, old_line: str, new_line: str) -> None:
    a, b = _TOKEN.findall(old_line), _TOKEN.findall(new_line)
    ops = SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()
    out.append("- ", style=_GUTTER)
    for tag, i1, i2, _j1, _j2 in ops:
        if tag == "equal":
            out.append("".join(a[i1:i2]), style=_DEL)
        elif tag in ("replace", "delete"):
            out.append("".join(a[i1:i2]), style=_DEL_HL)
    out.append("\n")
    out.append("+ ", style=_GUTTER)
    for tag, _i1, _i2, j1, j2 in ops:
        if tag == "equal":
            out.append("".join(b[j1:j2]), style=_INS)
        elif tag in ("replace", "insert"):
            out.append("".join(b[j1:j2]), style=_INS_HL)
    out.append("\n")
