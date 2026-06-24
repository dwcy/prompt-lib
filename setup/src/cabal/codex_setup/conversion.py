# -*- coding: utf-8 -*-
"""Read-only conversion manifest and audit helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cabal._paths import RESOURCE_ROOT
from cabal.codex_setup.paths import CODEX_SOURCE_DIR

VALID_KINDS = {"skill", "agent-role", "rule-reference", "template", "unsupported"}
VALID_STATUSES = {"converted", "not-converted", "codex-only", "stale", "unsupported"}


@dataclass(frozen=True)
class ConversionEntry:
    source: Path | None
    output: Path | None
    kind: str
    status: str
    reason: str

    @property
    def source_label(self) -> str:
        return _rel_label(self.source)

    @property
    def output_label(self) -> str:
        return _rel_label(self.output)


def _resolve(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    return RESOURCE_ROOT / path_value


def _rel_label(path: Path | None) -> str:
    if path is None:
        return "-"
    try:
        return path.relative_to(RESOURCE_ROOT).as_posix()
    except ValueError:
        return str(path)


def manifest_path() -> Path:
    return CODEX_SOURCE_DIR / "conversion-manifest.json"


def load_conversion_entries() -> list[ConversionEntry]:
    path = manifest_path()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    entries: list[ConversionEntry] = []
    for raw in data.get("entries", []):
        kind = raw.get("kind", "unsupported")
        if kind not in VALID_KINDS:
            kind = "unsupported"
        status = raw.get("status", "not-converted")
        if status not in VALID_STATUSES:
            status = "not-converted"
        entries.append(
            ConversionEntry(
                source=_resolve(raw.get("source")),
                output=_resolve(raw.get("output")),
                kind=str(kind),
                status=status,
                reason=str(raw.get("reason", "")),
            )
        )
    return entries


def audit_conversion_entries() -> list[ConversionEntry]:
    audited: list[ConversionEntry] = []
    for entry in load_conversion_entries():
        status = entry.status
        if status == "converted":
            if entry.source is None or entry.output is None:
                status = "not-converted"
            elif not entry.source.exists() or not entry.output.exists():
                status = "stale"
            elif entry.source.read_text(encoding="utf-8", errors="replace") == entry.output.read_text(
                encoding="utf-8", errors="replace"
            ):
                status = "converted"
            else:
                status = "converted"
        elif status == "codex-only" and entry.output is not None and not entry.output.exists():
            status = "stale"
        elif status in {"not-converted", "unsupported"} and entry.source is not None and not entry.source.exists():
            status = "stale"
        audited.append(
            ConversionEntry(
                source=entry.source,
                output=entry.output,
                kind=entry.kind,
                status=status,
                reason=entry.reason,
            )
        )
    return audited
