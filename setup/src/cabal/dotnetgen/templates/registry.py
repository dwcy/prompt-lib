# -*- coding: utf-8 -*-
"""The closed set of architecture templates, and the only place that set is defined.

FR-001 requires generation from a small closed set rather than per-run improvisation, and
FR-001c requires that an unknown id be an error and never a fallback. Both rules are enforced
here so that `cli.py`, `state.py` and the scaffolder cannot drift from one another - before this
module the tuple was written out twice and could.

**Declared is not the same as built.** All three members are declared from the start because the
closed set is what the spec, the CLI contract and the project state file all validate against.
Phase 3 builds only `vertical-slice`; `minimal-service` and `clean-arch` arrive in Phase 7b
(T023/T025). Asking for a declared-but-unbuilt template raises `TemplateNotBuiltError` naming the
task that builds it - the same explicit-deferral pattern `cli.NotWiredError` uses, not a stub that
scaffolds something wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

TEMPLATES_ROOT: Final[Path] = Path(__file__).parent


class TemplateError(ValueError):
    """Base for every template-resolution failure."""


class UnknownTemplateError(TemplateError):
    """Raised for an id outside the closed set. Never resolved by falling back to a default."""


class TemplateNotBuiltError(TemplateError):
    """Raised for a declared template whose files are scheduled in a later task."""

    def __init__(self, template_id: str, task: str) -> None:
        super().__init__(
            f"template {template_id!r} is declared in the closed set but not built yet - "
            f"it arrives in {task}; use {DEFAULT_TEMPLATE!r} until then"
        )
        self.template_id = template_id
        self.task = task


@dataclass(frozen=True)
class ArchitectureTemplate:
    """One member of the closed set: what it is, where its files live, and whether they exist."""

    id: str
    summary: str
    built_in_task: str

    @property
    def root(self) -> Path:
        return TEMPLATES_ROOT / self.id

    @property
    def is_built(self) -> bool:
        """True once the template's files exist on disk, not merely because it is declared."""
        return self.root.is_dir()


_TEMPLATES: Final[tuple[ArchitectureTemplate, ...]] = (
    ArchitectureTemplate(
        id="minimal-service",
        summary="single project, minimal API, feature folders, EF Core, no mediator",
        built_in_task="T023",
    ),
    ArchitectureTemplate(
        id="vertical-slice",
        summary="feature-folder slices, one handler per slice, EF Core",
        built_in_task="T024",
    ),
    ArchitectureTemplate(
        id="clean-arch",
        summary="Domain/Application/Infrastructure/Api layering with CQRS",
        built_in_task="T025",
    ),
)

TEMPLATE_IDS: Final[tuple[str, ...]] = tuple(template.id for template in _TEMPLATES)
DEFAULT_TEMPLATE: Final[str] = "vertical-slice"

_BY_ID: Final[dict[str, ArchitectureTemplate]] = {t.id: t for t in _TEMPLATES}


def all_templates() -> tuple[ArchitectureTemplate, ...]:
    """The closed set, in declaration order."""
    return _TEMPLATES


def get(template_id: str) -> ArchitectureTemplate:
    """Resolve an id to its template, or refuse. An unknown id is never silently defaulted."""
    try:
        return _BY_ID[template_id]
    except KeyError:
        raise UnknownTemplateError(
            f"unknown template {template_id!r}; expected one of {TEMPLATE_IDS}. "
            "The set is closed - it is not extended by asking for something else"
        ) from None


def require_built(template_id: str) -> ArchitectureTemplate:
    """Resolve an id and assert its files exist, for callers that are about to scaffold from it."""
    template = get(template_id)
    if not template.is_built:
        raise TemplateNotBuiltError(template.id, template.built_in_task)
    return template
