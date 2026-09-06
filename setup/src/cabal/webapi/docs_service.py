# -*- coding: utf-8 -*-
"""Read-only README summary and docs/ listing for the Docs reference module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_DOC_GLOB = "*.md"
_HEADING_PREFIX = "#"


def _first_heading_or_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        return stripped.lstrip(_HEADING_PREFIX).strip()
    return ""


def _readme_payload(project: Path) -> dict[str, Any] | None:
    for name in ("README.md", "Readme.md", "readme.md"):
        candidate = project / name
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            return {
                "path": name,
                "title": _first_heading_or_line(text) or name,
                "line_count": len(lines),
                "content": text,
            }
    return None


def _document_entries(project: Path) -> list[dict[str, Any]]:
    docs_dir = project / "docs"
    if not docs_dir.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(docs_dir.glob(_DOC_GLOB)):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        entries.append(
            {
                "name": path.name,
                "path": str(path.relative_to(project)).replace("\\", "/"),
                "description": _first_heading_or_line(text),
            }
        )
    return entries


def docs_payload(project: Path) -> dict[str, Any]:
    return {
        "readme": _readme_payload(project),
        "documents": _document_entries(project),
    }


def document_content(project: Path, relative_path: str) -> str | None:
    """Return a docs/ markdown file's content, or None if outside docs/ or missing."""
    docs_dir = (project / "docs").resolve()
    target = (project / relative_path).resolve()
    if docs_dir not in target.parents and target != docs_dir:
        return None
    if not target.is_file() or target.suffix.lower() != ".md":
        return None
    return target.read_text(encoding="utf-8", errors="replace")
