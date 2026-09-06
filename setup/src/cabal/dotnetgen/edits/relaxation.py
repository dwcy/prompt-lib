# -*- coding: utf-8 -*-
"""Locate literal text that has drifted, by progressively relaxing what counts as a match.

Text anchors are the fallback for edits that are not member-scoped: `using` directives, top-level
statements in `Program.cs`, `.csproj` items, DI registration lines. Symbols cannot address those,
so they need an anchor that tolerates the file having been reformatted since the model saw it.

The ladder is not an optimisation. Aider's measured result is that progressive relaxation is the
difference between an edit format that works and one that does not, and in this repo the pressure
is constant: `dotnet format` rewrites whitespace after every single write. An exact-match-only
applier would fail against its own tooling's output.

Each rung gives up one more thing:

  0 exact          the characters as given
  1 whitespace     runs of whitespace compare equal, so reflowing does not matter
  2 leading-trim   per-line indentation is dropped, so re-indenting does not matter
  3 token          punctuation is dropped too; the last resort before giving up

Every rung searches a *projection* of the source while keeping a map back to real offsets, so a
match found by ignoring whitespace still replaces the exact original characters. The rung that
succeeded is recorded, never hidden - `relaxation_level` is how a drifting codebase becomes
visible instead of silently costing retries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

RELAXATION_EXACT: Final[int] = 0
RELAXATION_WHITESPACE: Final[int] = 1
RELAXATION_LEADING_TRIM: Final[int] = 2
RELAXATION_TOKEN: Final[int] = 3

LADDER: Final[tuple[int, ...]] = (
    RELAXATION_EXACT,
    RELAXATION_WHITESPACE,
    RELAXATION_LEADING_TRIM,
    RELAXATION_TOKEN,
)

LADDER_NAMES: Final[dict[int, str]] = {
    RELAXATION_EXACT: "exact",
    RELAXATION_WHITESPACE: "whitespace-insensitive",
    RELAXATION_LEADING_TRIM: "leading-trim",
    RELAXATION_TOKEN: "normalised-token",
}


@dataclass(frozen=True)
class Match:
    """Where the search text was found, and how much relaxation it took to find it."""

    start: int
    end: int
    level: int

    @property
    def level_name(self) -> str:
        return LADDER_NAMES[self.level]


class AmbiguousMatchError(LookupError):
    """The search text occurs more than once. Editing a guess would corrupt the file."""


class AnchorNotFoundError(LookupError):
    """The search text could not be located at any rung of the ladder."""


def find(source: str, search: str) -> Match | None:
    """Walk the ladder, returning the first unambiguous match. None when every rung fails."""
    for level in LADDER:
        projected, offsets = _project(source, level)
        wanted, _ = _project(search, level)
        wanted = wanted.strip()
        if not wanted:
            continue

        first = projected.find(wanted)
        if first == -1:
            continue
        if projected.find(wanted, first + 1) != -1:
            raise AmbiguousMatchError(
                f"anchor text occurs more than once ({LADDER_NAMES[level]} match): {search[:80]!r}"
            )
        start = offsets[first]
        end = offsets[first + len(wanted) - 1] + 1
        end = _extend_over_dropped_tail(source, end, search, level)
        return Match(start=start, end=end, level=level)
    return None


def _extend_over_dropped_tail(source: str, end: int, search: str, level: int) -> int:
    """Grow the span to cover trailing characters the projection discarded.

    At the token rung `app.MapHealth();` projects to `app MapHealth`, so the raw match ends after
    `MapHealth` and the `();` is left behind. Replacing that span would splice new code in front
    of an orphaned `();` and break the file. The tail is only consumed when the source actually
    continues with the same characters the search ended with, so this can never swallow unrelated
    code.
    """
    tail = [c for c in _dropped_tail(search, level) if not c.isspace()]
    if not tail:
        return end

    cursor = end
    matched = 0
    while matched < len(tail) and cursor < len(source):
        if source[cursor].isspace():
            cursor += 1
            continue
        if source[cursor] != tail[matched]:
            break
        cursor += 1
        matched += 1
    return cursor if matched == len(tail) else end


def _dropped_tail(search: str, level: int) -> str:
    """The trailing run of `search` that this rung's projection throws away."""
    stripped = search.rstrip()
    index = len(stripped)
    while index > 0 and _is_dropped(stripped[index - 1], level):
        index -= 1
    return stripped[index:]


def _is_dropped(char: str, level: int) -> bool:
    if char.isspace():
        return level >= RELAXATION_WHITESPACE
    return level >= RELAXATION_TOKEN and not (char.isalnum() or char == "_")


def replace(source: str, search: str, content: str) -> tuple[str, Match]:
    """Replace the located span with `content`. Raises when the anchor is missing or not unique."""
    match = find(source, search)
    if match is None:
        raise AnchorNotFoundError(
            f"anchor text not found at any relaxation level: {search[:80]!r}"
        )
    return source[: match.start] + content + source[match.end :], match


def _project(text: str, level: int) -> tuple[str, list[int]]:
    """Project `text` for one rung, returning the projection and its map back to real offsets."""
    if level == RELAXATION_EXACT:
        return text, list(range(len(text)))

    out: list[str] = []
    offsets: list[int] = []
    index = 0
    length = len(text)
    at_line_start = True

    while index < length:
        char = text[index]

        if char.isspace():
            run_end = index
            while run_end < length and text[run_end].isspace():
                run_end += 1
            crossed_newline = "\n" in text[index:run_end]

            drop = level >= RELAXATION_LEADING_TRIM and (at_line_start or crossed_newline)
            if not drop and out and out[-1] != " ":
                out.append(" ")
                offsets.append(index)

            at_line_start = crossed_newline if level >= RELAXATION_LEADING_TRIM else False
            index = run_end
            continue

        if level >= RELAXATION_TOKEN and not (char.isalnum() or char == "_"):
            if out and out[-1] != " ":
                out.append(" ")
                offsets.append(index)
            index += 1
            at_line_start = False
            continue

        out.append(char)
        offsets.append(index)
        at_line_start = False
        index += 1

    return "".join(out), offsets
