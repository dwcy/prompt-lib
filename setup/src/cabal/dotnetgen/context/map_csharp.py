# -*- coding: utf-8 -*-
"""Parse C# into declarations, and render a structural map of signatures without bodies.

This is the module that decides how much of a solution the model ever sees. FR-005 wants the
shape of the code, not the code: a map of types and member signatures, with every member body
omitted. Sending bodies speculatively is the single largest input-token waste in naive pipelines.

**Syntax level, not semantic.** Phase A parses text - it tracks braces, strings and comments, and
reads declaration headers. It does not resolve types, follow references, or understand generics
beyond their spelling. That is deliberate (research R2): a solution generated from a known
template has a structure the template already dictates, so paying for a Roslyn semantic model to
rediscover it would be waste. Brownfield is where semantics earn their cost, and that is Phase B.

Known limits, stated rather than hidden: nested types are recorded flat under their outer type,
explicit interface implementations keep their qualified spelling, and `#if` regions are parsed as
if every branch were live.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

TYPE_KEYWORDS: Final[tuple[str, ...]] = ("class", "record", "struct", "interface", "enum")

_NAMESPACE = re.compile(r"\bnamespace\s+(?P<name>[\w.]+)\s*[;{]")
_TYPE_HEADER = re.compile(
    r"(?P<modifiers>(?:\b(?:public|private|protected|internal|static|sealed|abstract|partial|readonly|file)\s+)*)"
    r"\b(?P<kind>class|record|struct|interface|enum)\s+"
    r"(?P<name>[A-Za-z_]\w*)"
    r"(?P<generics><[^>{;]*>)?"
)
_MEMBER_HEADER = re.compile(
    r"(?P<modifiers>(?:\b(?:public|private|protected|internal|static|virtual|override|sealed|abstract|async|extern|new|readonly|const|partial|required|unsafe)\s+)*)"
    r"(?P<signature>[\w<>\[\],.?\s]+?\s+)?"
    r"(?P<name>[A-Za-z_][\w.]*)"
    r"(?P<generics><[^>(]*>)?"
    r"\s*(?P<params>\([^)]*\))?"
    r"\s*$"
)

_LINE_COMMENT = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)


@dataclass(frozen=True)
class Declaration:
    """One parsed declaration, with the source span it occupies."""

    kind: str
    name: str
    namespace: str
    container: str
    signature: str
    start: int
    end: int

    @property
    def qualified(self) -> str:
        """`Namespace.Type` for a type, `Namespace.Type.Member` for a member."""
        parts = [p for p in (self.namespace, self.container, self.name) if p]
        return ".".join(parts)

    @property
    def is_type(self) -> bool:
        return self.kind in TYPE_KEYWORDS


def blank_noise(source: str) -> str:
    """Replace comments and string contents with spaces, preserving every offset.

    Brace matching and header regexes both run over this. Offsets must not shift, or every span
    this module reports would be wrong by the length of the comments above it.
    """
    out = list(source)

    def blank(match: re.Match[str]) -> None:
        for i in range(match.start(), match.end()):
            if out[i] != "\n":
                out[i] = " "

    scrubbed = source
    for pattern in (_BLOCK_COMMENT, _LINE_COMMENT):
        for match in pattern.finditer(scrubbed):
            blank(match)
        scrubbed = "".join(out)

    index = 0
    length = len(scrubbed)
    while index < length:
        char = scrubbed[index]
        if char in ('"', "'"):
            verbatim = index > 0 and scrubbed[index - 1] == "@"
            index += 1
            while index < length:
                current = scrubbed[index]
                if current == "\\" and not verbatim:
                    out[index] = " "
                    index += 2
                    continue
                if current == char:
                    break
                if current != "\n":
                    out[index] = " "
                index += 1
        index += 1
    return "".join(out)


def parse(source: str) -> tuple[Declaration, ...]:
    """Extract every type and member declaration, outermost first, in source order."""
    scrubbed = blank_noise(source)
    namespace = _namespace_of(scrubbed)
    declarations: list[Declaration] = []
    _walk(scrubbed, 0, len(scrubbed), namespace, "", declarations)
    return tuple(declarations)


def _namespace_of(scrubbed: str) -> str:
    match = _NAMESPACE.search(scrubbed)
    return match.group("name") if match else ""


def _walk(
    scrubbed: str,
    start: int,
    stop: int,
    namespace: str,
    container: str,
    out: list[Declaration],
) -> None:
    """Scan one brace level, recording declarations and recursing into type bodies."""
    index = start
    header_start = start
    while index < stop:
        char = scrubbed[index]
        if char == ";":
            _record(scrubbed, header_start, index, index + 1, namespace, container, out)
            index += 1
            header_start = index
            continue
        if char == "{":
            body_end = _matching_brace(scrubbed, index, stop)
            declaration = _record(
                scrubbed, header_start, index, body_end + 1, namespace, container, out
            )
            if declaration is not None and declaration.is_type:
                inner = declaration.name if not container else f"{container}.{declaration.name}"
                _walk(scrubbed, index + 1, body_end, namespace, inner, out)
            index = body_end + 1
            header_start = index
            continue
        if char == "}":
            index += 1
            header_start = index
            continue
        index += 1


def _record(
    scrubbed: str,
    header_start: int,
    header_stop: int,
    end: int,
    namespace: str,
    container: str,
    out: list[Declaration],
) -> Declaration | None:
    header = scrubbed[header_start:header_stop].strip()
    if not header or header.startswith(("using", "namespace", "[", "#")):
        return None

    type_match = _TYPE_HEADER.search(header)
    if type_match is not None:
        declaration = Declaration(
            kind=type_match.group("kind"),
            name=type_match.group("name"),
            namespace=namespace,
            container=container,
            signature=_collapse(header),
            start=header_start + (len(scrubbed[header_start:header_stop]) - len(scrubbed[header_start:header_stop].lstrip())),
            end=end,
        )
        out.append(declaration)
        return declaration

    if not container:
        return None

    member_match = _MEMBER_HEADER.search(_collapse(header))
    if member_match is None or not member_match.group("name"):
        return None
    declaration = Declaration(
        kind="method" if member_match.group("params") else "member",
        name=member_match.group("name"),
        namespace=namespace,
        container=container,
        signature=_collapse(header),
        start=header_start + (len(scrubbed[header_start:header_stop]) - len(scrubbed[header_start:header_stop].lstrip())),
        end=end,
    )
    out.append(declaration)
    return declaration


def _matching_brace(scrubbed: str, open_index: int, stop: int) -> int:
    depth = 0
    for index in range(open_index, stop):
        if scrubbed[index] == "{":
            depth += 1
        elif scrubbed[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return stop - 1


def _collapse(text: str) -> str:
    return " ".join(text.split())


def render(path: str, source: str) -> str:
    """One file's contribution to the structural map: signatures only, never a body."""
    lines = [f"{path}:"]
    for declaration in parse(source):
        indent = "  " if declaration.is_type else "    "
        lines.append(f"{indent}{declaration.signature}")
    return "\n".join(lines)
