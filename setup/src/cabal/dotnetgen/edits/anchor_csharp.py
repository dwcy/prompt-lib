# -*- coding: utf-8 -*-
"""Resolve a fully-qualified C# symbol to the source span it occupies.

This is the anchor that makes edits survive this repo's own tooling. `dotnet format` runs as a
`PostToolUse` hook after every write (`global/rules/csharp.md`), which rewrites whitespace and can
reorder members - a systematic generator of anchor drift. Any text-anchored edit format would be
fighting that hook on every single turn.

A symbol is invariant under all of it. `Api.Features.Health.HealthEndpoint.MapHealth` names the
same member before and after formatting, so the anchor is re-resolved against the current file at
apply time and simply cannot go stale (research R1).

Resolution is deliberately forgiving about *spelling* and strict about *ambiguity*: a caller may
name a member with or without its parameter list, but if that leaves more than one candidate the
resolution fails rather than guessing which overload was meant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cabal.dotnetgen.context.map_csharp import Declaration, parse

_PARAMS = re.compile(r"\s*\(.*\)\s*$", re.S)


class AnchorError(LookupError):
    """Raised when a symbol cannot be resolved to exactly one declaration."""


class SymbolNotFoundError(AnchorError):
    """The symbol names nothing in this file."""


class AmbiguousSymbolError(AnchorError):
    """The symbol names more than one declaration - usually an overload set."""


@dataclass(frozen=True)
class Span:
    """A resolved region of a source file, as character offsets."""

    start: int
    end: int
    declaration: Declaration

    def replaced_with(self, source: str, content: str) -> str:
        """The file's new text with this span swapped for `content`, indentation preserved."""
        indent = _indent_at(source, self.start)
        return source[: self.start] + _reindent(content, indent) + source[self.end :]


def resolve(source: str, symbol: str) -> Span:
    """Locate `symbol` in `source`. Raises rather than returning a best guess."""
    wanted = _normalise(symbol)
    declarations = parse(source)

    exact = [d for d in declarations if _normalise(d.qualified) == wanted]
    if len(exact) == 1:
        return Span(exact[0].start, exact[0].end, exact[0])
    if len(exact) > 1:
        raise AmbiguousSymbolError(
            f"{symbol!r} matches {len(exact)} declarations; name the overload's parameter list"
        )

    # Fall back to a suffix match so a caller may omit the namespace, which is the common case
    # when the writing stage has only seen the structural map.
    suffix = [d for d in declarations if _normalise(d.qualified).endswith("." + wanted)]
    if len(suffix) == 1:
        return Span(suffix[0].start, suffix[0].end, suffix[0])
    if len(suffix) > 1:
        raise AmbiguousSymbolError(
            f"{symbol!r} is ambiguous - it matches {', '.join(d.qualified for d in suffix)}"
        )

    known = ", ".join(d.qualified for d in declarations) or "nothing"
    raise SymbolNotFoundError(f"{symbol!r} not found; this file declares {known}")


def contains(source: str, symbol: str) -> bool:
    """True when the symbol resolves unambiguously. Never raises."""
    try:
        resolve(source, symbol)
    except AnchorError:
        return False
    return True


def insert_into_type(source: str, type_symbol: str, content: str) -> str:
    """Add a member at the end of a type's body, before its closing brace."""
    span = resolve(source, type_symbol)
    if not span.declaration.is_type:
        raise AnchorError(f"{type_symbol!r} is a {span.declaration.kind}, not a type")

    closing = source.rfind("}", span.start, span.end)
    if closing == -1:
        raise AnchorError(f"{type_symbol!r} has no body to insert into")

    member_indent = _indent_at(source, span.start) + "    "
    block = _reindent(content, member_indent)
    return source[:closing] + block + "\n" + source[closing:]


def _normalise(symbol: str) -> str:
    """Drop a parameter list and collapse whitespace so spellings compare equal."""
    return _PARAMS.sub("", symbol).strip()


def _indent_at(source: str, offset: int) -> str:
    line_start = source.rfind("\n", 0, offset) + 1
    return source[line_start:offset] if source[line_start:offset].strip() == "" else ""


def _reindent(content: str, indent: str) -> str:
    """Re-indent a block to `indent`, leaving its internal relative shape intact."""
    lines = content.strip("\n").splitlines()
    if not lines:
        return ""
    existing = min(
        (len(line) - len(line.lstrip()) for line in lines if line.strip()),
        default=0,
    )
    rebuilt = [indent + line[existing:] if line.strip() else "" for line in lines]
    return "\n".join(rebuilt)
