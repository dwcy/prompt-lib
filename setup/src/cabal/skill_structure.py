# -*- coding: utf-8 -*-
"""Turns a skill's markdown body into the structure the UI renders: a heading outline with
typed blocks per section, the cross-references it names (other skills, agents, MCP tools,
files), and the files bundled next to its SKILL.md."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

MAX_REFERENCES_PER_GROUP = 40
MAX_BUNDLED_FILES = 200

TEXT_SUFFIXES = frozenset(
    {
        ".md",
        ".txt",
        ".json",
        ".jsonc",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".css",
        ".html",
        ".sh",
        ".ps1",
        ".cmd",
        ".bat",
        ".sql",
        ".csv",
        ".tmpl",
        ".example",
    }
)

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_ORDERED = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")
_TABLE_DIVIDER = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
_ANCHOR_STRIP = re.compile(r"[^a-z0-9]+")

_SKILL_MENTION = re.compile(r"(?<![\w/])/([a-z][a-z0-9-]{1,60}(?::[a-z0-9-]{1,60})?)\b")
_AGENT_MENTION = re.compile(r"(?<![\w/])@([a-z][a-z0-9-]{2,60})\b")
_TOOL_MENTION = re.compile(r"\bmcp__[A-Za-z0-9_]+\b")
_INLINE_CODE = re.compile(r"`([^`\n]{2,200})`")


def anchor_for(title: str, used: set[str]) -> str:
    base = _ANCHOR_STRIP.sub("-", title.lower()).strip("-") or "section"
    anchor = base
    suffix = 2
    while anchor in used:
        anchor = f"{base}-{suffix}"
        suffix += 1
    used.add(anchor)
    return anchor


def _paragraph(buffer: list[str]) -> dict[str, Any] | None:
    text = "\n".join(buffer).strip()
    buffer.clear()
    return {"type": "paragraph", "text": text} if text else None


def _table_block(rows: list[str]) -> dict[str, Any]:
    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    header = cells(rows[0])
    body = [cells(row) for row in rows[2:]]
    return {"type": "table", "header": header, "rows": body}


def parse_blocks(body: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split a markdown body into (preamble_blocks, sections).

    Sections are flat and carry their heading level, so the UI can indent or collapse them
    without a nested tree. Everything before the first heading lands in the preamble.
    """
    lines = body.splitlines()
    preamble: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = preamble
    anchors: set[str] = set()
    text_buffer: list[str] = []
    index = 0

    def flush() -> None:
        block = _paragraph(text_buffer)
        if block is not None:
            current.append(block)

    while index < len(lines):
        line = lines[index]
        fence = _FENCE.match(line)
        if fence is not None:
            flush()
            marker, language = fence.group(1), fence.group(2)
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith(marker[0] * 3):
                code.append(lines[index])
                index += 1
            index += 1
            current.append(
                {"type": "code", "language": language or None, "text": "\n".join(code)}
            )
            continue

        heading = _HEADING.match(line)
        if heading is not None:
            flush()
            title = heading.group(2).strip()
            section = {
                "level": len(heading.group(1)),
                "title": title,
                "anchor": anchor_for(title, anchors),
                "blocks": [],
            }
            sections.append(section)
            current = section["blocks"]
            index += 1
            continue

        if line.strip() in ("---", "***", "___"):
            flush()
            current.append({"type": "divider"})
            index += 1
            continue

        if line.lstrip().startswith("|") and index + 1 < len(lines) and _TABLE_DIVIDER.match(lines[index + 1]):
            flush()
            rows = [lines[index], lines[index + 1]]
            index += 2
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                rows.append(lines[index])
                index += 1
            current.append(_table_block(rows))
            continue

        bullet = _BULLET.match(line)
        ordered = _ORDERED.match(line)
        if bullet is not None or ordered is not None:
            flush()
            block, index = _read_list(lines, index)
            current.append(block)
            continue

        if line.strip().startswith(">"):
            flush()
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip().lstrip(">").strip())
                index += 1
            current.append({"type": "quote", "text": "\n".join(quote).strip()})
            continue

        if not line.strip():
            flush()
            index += 1
            continue

        text_buffer.append(line)
        index += 1

    flush()
    return preamble, sections


def _read_list(lines: list[str], index: int) -> tuple[dict[str, Any], int]:
    items: list[dict[str, Any]] = []
    ordered_list = _ORDERED.match(lines[index]) is not None
    while index < len(lines):
        line = lines[index]
        match = _ORDERED.match(line) if ordered_list else _BULLET.match(line)
        other = _BULLET.match(line) if ordered_list else _ORDERED.match(line)
        if match is not None:
            items.append({"text": match.group(2).strip(), "depth": len(match.group(1)) // 2})
            index += 1
            continue
        if other is not None:
            items.append({"text": other.group(2).strip(), "depth": len(other.group(1)) // 2})
            index += 1
            continue
        # An indented continuation line belongs to the item above it.
        if line.startswith((" ", "\t")) and line.strip() and items:
            items[-1]["text"] = f"{items[-1]['text']} {line.strip()}"
            index += 1
            continue
        break
    return {"type": "list", "ordered": ordered_list, "items": items}, index


# -- cross references ----------------------------------------------------


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)[:MAX_REFERENCES_PER_GROUP]


def extract_references(
    body: str,
    *,
    self_invocation: str,
    known_skills: dict[str, str],
    known_agents: Iterable[str],
    path_roots: Iterable[Path],
) -> dict[str, list[dict[str, Any]]]:
    """The other pieces of the setup a skill body names, each marked resolved or not.

    `known_skills` maps an invocation (`/tui`) to the skill id it resolves to, so the UI can
    jump straight there; unresolved mentions are still listed, because a skill pointing at
    something that is not installed is exactly what you want to see.
    """
    agents = {name.lower() for name in known_agents}
    skills: list[dict[str, Any]] = []
    for name in _dedupe(match.group(1) for match in _SKILL_MENTION.finditer(body)):
        invocation = f"/{name}"
        if invocation == self_invocation:
            continue
        skills.append({"label": invocation, "target_id": known_skills.get(invocation)})

    # `@property` / `@dataclass` in a code sample is not an agent reference. An unresolved
    # mention only counts when it is hyphenated the way every agent name is, so a skill pointing
    # at an agent that is not installed still shows up.
    agent_refs = [
        {"label": f"@{name}", "target_id": None, "resolved": name.lower() in agents}
        for name in _dedupe(match.group(1) for match in _AGENT_MENTION.finditer(body))
        if name.lower() in agents or "-" in name
    ]
    tool_refs = [
        {"label": name, "target_id": None, "resolved": True}
        for name in _dedupe(_TOOL_MENTION.findall(body))
    ]
    file_refs = _file_references(body, path_roots)
    return {
        "skills": [{**ref, "resolved": ref["target_id"] is not None} for ref in skills],
        "agents": agent_refs,
        "tools": tool_refs,
        "files": file_refs,
    }


def _file_references(body: str, path_roots: Iterable[Path]) -> list[dict[str, Any]]:
    """Backticked paths that actually resolve under one of `path_roots`.

    Only real hits are listed — an inline `code` span is far more often a flag or a symbol than
    a path, and a list of guesses would be worse than no list.
    """
    roots = [root for root in path_roots if root is not None]
    candidates = _dedupe(
        candidate
        for candidate in (match.group(1).strip() for match in _INLINE_CODE.finditer(body))
        if "/" in candidate and " " not in candidate and not candidate.startswith(("http", "-"))
    )
    references: list[dict[str, Any]] = []
    for candidate in candidates:
        cleaned = candidate.strip("`").lstrip("./")
        if cleaned.startswith("~/"):
            resolved = Path.home() / cleaned[2:]
            if resolved.exists():
                references.append({"label": candidate, "path": str(resolved), "resolved": True})
            continue
        for root in roots:
            resolved = root / cleaned
            if resolved.exists():
                references.append({"label": candidate, "path": str(resolved), "resolved": True})
                break
    return references


# -- bundled files -------------------------------------------------------


def bundled_files(skill_dir: Path | None) -> list[dict[str, Any]]:
    """Every file the skill folder ships besides SKILL.md, grouped by its top-level folder."""
    if skill_dir is None or not skill_dir.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    try:
        children = sorted(skill_dir.rglob("*"), key=lambda item: item.as_posix().lower())
    except OSError:
        return []
    for child in children:
        if len(entries) >= MAX_BUNDLED_FILES:
            break
        if not child.is_file() or child.name == "SKILL.md":
            continue
        relative = child.relative_to(skill_dir)
        parts = relative.parts
        try:
            size = child.stat().st_size
        except OSError:
            size = None
        entries.append(
            {
                "name": child.name,
                "rel_path": relative.as_posix(),
                "group": parts[0] if len(parts) > 1 else "",
                "size_bytes": size,
                "previewable": child.suffix.lower() in TEXT_SUFFIXES,
            }
        )
    return entries
