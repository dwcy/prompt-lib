# -*- coding: utf-8 -*-
"""Content-addressed cache for the structural map.

The map sits in cache band 3, above the volatile turn content and below the locked rules. That
placement only pays off if the map is *byte-identical* when the solution has not changed - a map
that differs by so much as a reordered line invalidates the prefix beneath it and takes the whole
cached prefix with it (research R5).

So the map is keyed on a fingerprint of the solution's shape, and a hit returns the stored bytes
rather than re-rendering. Re-rendering would usually produce the same text, but "usually" is not
a property a cache can be built on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from cabal.dotnetgen import intent, state
from cabal.dotnetgen.context.structural_map import StructuralMap, build
from cabal.dotnetgen.templates import registry

CACHE_RELPATH: Final[str] = ".dotnetgen/map-cache"


def cache_path(project: Path, fingerprint: str, token_budget: int) -> Path:
    """One file per (fingerprint, budget). A different budget is a different map."""
    digest = fingerprint.split(":")[-1][:16]
    return project / CACHE_RELPATH / f"{digest}-{token_budget}.txt"


def rendered_map(
    project: Path, *, token_budget: int, write_cache: bool = True
) -> tuple[str, StructuralMap]:
    """Return the map text and the map itself, reading through the cache."""
    fingerprint = intent.solution_fingerprint(project)
    built = build(
        project,
        fingerprint=fingerprint,
        token_budget=token_budget,
        template=_template_for(project),
        recent_types=_recent_types(project),
    )

    path = cache_path(project, fingerprint, token_budget)
    if path.is_file():
        return path.read_text(encoding="utf-8"), built

    rendered = built.render()
    if not write_cache:
        return rendered, built
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")
    except OSError:
        # A cache that cannot be written is a performance loss, never a correctness one.
        pass
    return rendered, built


def _template_for(project: Path) -> registry.ArchitectureTemplate | None:
    if not state.exists(project):
        return None
    try:
        return registry.get(state.load(project).template_id)
    except (state.StateError, registry.TemplateError):
        return None


def _recent_types(project: Path) -> tuple[str, ...]:
    if not state.exists(project):
        return ()
    try:
        return state.load(project).recent_types
    except state.StateError:
        return ()
