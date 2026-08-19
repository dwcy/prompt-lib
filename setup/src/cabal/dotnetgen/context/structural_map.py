# -*- coding: utf-8 -*-
"""Build a ranked, budgeted structural map of a solution — and say what it left out.

This is the artifact that decides how much of a codebase the model ever sees before it opens a
file. Two rules give it its value:

* **Signatures, never bodies.** Sending bodies speculatively is the largest input-token waste in
  naive pipelines, and SC-006 wants the map under 2% of source size.
* **Silent truncation is a defect, not a trade-off.** When the budget binds, `omitted_count` and
  `omitted_summary` say what was dropped (FR-006). A map that quietly stops at the budget looks
  identical to a complete one, so the model reasons over a codebase it thinks it has seen.

Ranking is (layer, visibility, recency) per research R3 — no reference graph, no semantic model.
A template-generated solution already declares its layering in the project references, public
members are the API by definition, and the run records already track recently touched types. The
ranking's real job is tie-breaking inside a budget that signatures-only extraction usually clears
by an order of magnitude; PageRank is a Phase B decision to be triggered by evidence, not guessed
at now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from cabal.dotnetgen.context.map_csharp import Declaration, parse
from cabal.dotnetgen.templates.registry import ArchitectureTemplate

CHARS_PER_TOKEN: Final[int] = 4
"""Rough chars-to-tokens ratio used to enforce the budget without a tokenizer dependency.

Deliberately an estimate. The budget is a cost guard, not an accounting figure, and pulling in a
tokenizer to police a heuristic map would cost more than it saves.
"""

VISIBILITY_ORDER: Final[dict[str, int]] = {
    "public": 0,
    "protected": 1,
    "internal": 2,
    "private": 3,
}

SOURCE_GLOB: Final[str] = "*.cs"
IGNORED_DIRS: Final[frozenset[str]] = frozenset({"obj", "bin", "node_modules", "packages"})


@dataclass(frozen=True)
class SymbolEntry:
    """One type and its member signatures, with the ranking inputs that ordered it."""

    project: str
    namespace: str
    type_name: str
    kind: str
    visibility: str
    layer: str
    members: tuple[str, ...]
    path: str

    def render(self) -> str:
        head = f"{self.path}  [{self.layer}]"
        lines = [head, f"  {self.visibility} {self.kind} {self.type_name}"]
        lines.extend(f"    {member}" for member in self.members)
        return "\n".join(lines)


@dataclass(frozen=True)
class StructuralMap:
    """The rendered map plus an honest account of what the budget removed."""

    fingerprint: str
    entries: tuple[SymbolEntry, ...] = field(default=())
    token_budget: int = 0
    omitted_count: int = 0
    omitted_summary: str | None = None

    def render(self) -> str:
        body = "\n".join(entry.render() for entry in self.entries)
        if self.omitted_count:
            body += f"\n\n[omitted] {self.omitted_summary}"
        return body

    @property
    def estimated_tokens(self) -> int:
        return len(self.render()) // CHARS_PER_TOKEN


def build(
    project: Path,
    *,
    fingerprint: str,
    token_budget: int,
    template: ArchitectureTemplate | None = None,
    recent_types: tuple[str, ...] = (),
) -> StructuralMap:
    """Scan the solution's C# sources and rank them into a map that fits the budget."""
    entries = _collect(project, template)
    ranked = sorted(entries, key=lambda e: _rank(e, recent_types))

    kept: list[SymbolEntry] = []
    budget_chars = token_budget * CHARS_PER_TOKEN
    used = 0
    for entry in ranked:
        rendered = len(entry.render()) + 1
        if used + rendered > budget_chars and kept:
            break
        kept.append(entry)
        used += rendered

    dropped = ranked[len(kept) :]
    return StructuralMap(
        fingerprint=fingerprint,
        entries=tuple(kept),
        token_budget=token_budget,
        omitted_count=len(dropped),
        omitted_summary=_summarise(dropped) if dropped else None,
    )


def _collect(project: Path, template: ArchitectureTemplate | None) -> list[SymbolEntry]:
    layers = _layers_for(template)
    entries: list[SymbolEntry] = []
    for path in sorted(project.rglob(SOURCE_GLOB)):
        relative = path.relative_to(project)
        if IGNORED_DIRS.intersection(relative.parts) or any(
            part.startswith(".") for part in relative.parts
        ):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        entries.extend(_entries_for(relative, source, layers))
    return entries


def _entries_for(
    relative: Path, source: str, layers: dict[str, str]
) -> list[SymbolEntry]:
    declarations = parse(source)
    types = [d for d in declarations if d.is_type]
    posix = relative.as_posix()
    project_name, layer = _owning_project(posix, layers)

    built: list[SymbolEntry] = []
    for declaration in types:
        members = tuple(
            d.signature
            for d in declarations
            if not d.is_type and d.container.split(".")[0] == declaration.name
        )
        built.append(
            SymbolEntry(
                project=project_name,
                namespace=declaration.namespace,
                type_name=declaration.name,
                kind=declaration.kind,
                visibility=_visibility_of(declaration),
                layer=layer,
                members=members,
                path=posix,
            )
        )
    return built


def _layers_for(template: ArchitectureTemplate | None) -> dict[str, str]:
    """Map a project's source directory to its declared layer, from the locked template."""
    if template is None:
        return {}
    return {spec.path: spec.layer for spec in template.project_layout}


def _owning_project(posix: str, layers: dict[str, str]) -> tuple[str, str]:
    for prefix, layer in layers.items():
        if posix.startswith(prefix + "/"):
            return prefix, layer
    return posix.rsplit("/", 1)[0] if "/" in posix else "", "unknown"


def _visibility_of(declaration: Declaration) -> str:
    for visibility in VISIBILITY_ORDER:
        if f"{visibility} " in declaration.signature:
            return visibility
    return "internal"


def _rank(entry: SymbolEntry, recent_types: tuple[str, ...]) -> tuple[int, int, int, str]:
    """(layer, visibility, recency, name) — cheap, deterministic, and free of graph construction."""
    layer_rank = _LAYER_ORDER.get(entry.layer, len(_LAYER_ORDER))
    visibility_rank = VISIBILITY_ORDER.get(entry.visibility, len(VISIBILITY_ORDER))
    try:
        recency = recent_types.index(entry.type_name)
    except ValueError:
        recency = len(recent_types)
    return (layer_rank, visibility_rank, recency, entry.type_name)


_LAYER_ORDER: Final[dict[str, int]] = {
    "domain": 0,
    "application": 1,
    "infrastructure": 2,
    "api": 3,
    "tests": 4,
}


def _summarise(dropped: list[SymbolEntry]) -> str:
    """Name what the budget removed, grouped by layer, so the omission is legible."""
    by_layer: dict[str, list[str]] = {}
    for entry in dropped:
        by_layer.setdefault(entry.layer, []).append(entry.type_name)
    parts = [
        f"{layer}: {', '.join(sorted(names)[:8])}"
        + (f" and {len(names) - 8} more" if len(names) > 8 else "")
        for layer, names in sorted(by_layer.items())
    ]
    return f"{len(dropped)} type(s) dropped by the token budget — " + "; ".join(parts)
