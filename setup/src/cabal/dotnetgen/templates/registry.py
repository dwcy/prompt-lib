# -*- coding: utf-8 -*-
"""The closed set of architecture templates, and the only place that set is defined.

FR-001 requires generation from a small closed set rather than per-run improvisation, and
FR-001c requires that an unknown id be an error and never a fallback. Both rules are enforced
here so that `cli.py`, `state.py` and the scaffolder cannot drift from one another - before this
module the tuple was written out twice and could.

**Declared is not the same as built.** All three members are declared from the start because the
closed set is what the spec, the CLI contract and the project state file all validate against.
Phase 3 builds only `vertical-slice`; `minimal-service` and `clean-arch` arrive in Phase 7b
(T023/T025). Asking to scaffold a declared-but-unbuilt template raises `TemplateNotBuiltError`
naming the task that builds it - the same explicit-deferral pattern `cli.NotWiredError` uses,
rather than a stub that scaffolds something structurally wrong.

**Templates are a `dotnet new` recipe, not a copied file tree** (data-model *ArchitectureTemplate*,
plan *Delivery Form*). FR-003 requires the first model turn to edit a solution that already
builds, so a template is the invocation sequence that produces that runnable skeleton plus the
convention overlay applied on top of it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cabal._paths import GLOBAL_DIR

TEMPLATES_ROOT: Final[Path] = Path(__file__).parent

PINNED_RULES: Final[tuple[str, ...]] = ("rules/csharp.md", "rules/_size-discipline.md")
"""Rule files every template inherits unchanged - the band-2 cacheable constant (research R5)."""

SOLUTION_NAME_PLACEHOLDER: Final[str] = "<solution>"
"""Stands in for the caller's solution name when a recipe is rendered for display."""


class TemplateError(ValueError):
    """Base for every template-resolution failure."""


class UnknownTemplateError(TemplateError):
    """Raised for an id outside the closed set. Never resolved by falling back to a default."""


class TemplateNotBuiltError(TemplateError):
    """Raised for a declared template whose overlay is scheduled in a later task."""

    def __init__(self, template_id: str, task: str) -> None:
        super().__init__(
            f"template {template_id!r} is declared in the closed set but not built yet - "
            f"it arrives in {task}; use {DEFAULT_TEMPLATE!r} until then"
        )
        self.template_id = template_id
        self.task = task


@dataclass(frozen=True)
class ProjectSpec:
    """One `.csproj` in a template's layout, and the edges it declares."""

    name: str
    kind: str
    """`dotnet new` short name - `webapi`, `classlib`, `xunit`."""
    path: str
    layer: str
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArchitectureTemplate:
    """The locked project shape. Static data shipped with the tool, never user-authored."""

    id: str
    display_name: str
    summary: str
    project_layout: tuple[ProjectSpec, ...]
    layer_order: tuple[str, ...]
    built_in_task: str
    prune: tuple[str, ...] = ()
    """Files `dotnet new` emits that the overlay does not want - sample classes, sample requests.

    Removed after scaffolding and before the overlay is copied. Files the overlay *replaces*
    (`Program.cs`, the `.csproj` files, `appsettings.json`) are not listed: the copy overwrites
    them, and listing them too would make the two mechanisms disagree about who owns the file.
    """

    def __post_init__(self) -> None:
        uncovered = {p.layer for p in self.project_layout} - set(self.layer_order)
        if uncovered:
            raise TemplateError(
                f"template {self.id!r}: layer_order must cover every project layer; "
                f"missing {sorted(uncovered)}"
            )
        names = {p.name for p in self.project_layout}
        for project in self.project_layout:
            dangling = set(project.references) - names
            if dangling:
                raise TemplateError(
                    f"template {self.id!r}: project {project.name!r} references "
                    f"{sorted(dangling)}, which is not in the layout"
                )

    @property
    def overlay_root(self) -> Path:
        """Convention files copied over the `dotnet new` output."""
        return TEMPLATES_ROOT / self.id

    @property
    def is_built(self) -> bool:
        """True once the overlay exists on disk, not merely because the id is declared."""
        return self.overlay_root.is_dir()

    def scaffold_steps(self, solution_name: str = SOLUTION_NAME_PLACEHOLDER) -> tuple[tuple[str, ...], ...]:
        """The `dotnet new` invocation and post-steps as argv, never a shell string.

        Steps carry the subcommand only - `verify.dotnet.run_command` supplies the resolved
        `dotnet` executable, so repeating it here would double it.

        The solution takes the caller's name; only the project names come from the layout, so
        two services built from one template are not both called `vertical-slice`.
        """
        steps: list[tuple[str, ...]] = [("new", "sln", "--name", solution_name)]
        steps.extend(
            ("new", p.kind, "--output", p.path, "--name", p.name) for p in self.project_layout
        )
        steps.extend(("sln", "add", f"{p.path}/{p.name}.csproj") for p in self.project_layout)
        return tuple(steps)

    @property
    def scaffold_command(self) -> str:
        """The step sequence rendered for display and for the run record (data-model)."""
        return " && ".join(f"dotnet {' '.join(step)}" for step in self.scaffold_steps())

    @property
    def conventions_digest(self) -> str:
        """Content hash of the pinned rule files, for cache-band-2 invalidation."""
        digest = hashlib.sha256()
        for relpath in PINNED_RULES:
            digest.update(relpath.encode("utf-8"))
            digest.update((GLOBAL_DIR / relpath).read_bytes())
        return f"sha256:{digest.hexdigest()}"

    def contract_text(self) -> str:
        """The band-2 template contract handed to `context.bands.build`."""
        lines = [f"Architecture template: {self.display_name} ({self.id}) - locked for this project.", self.summary, "", "Projects:"]
        lines.extend(
            f"  {p.path}/{p.name}.csproj  [{p.layer}]"
            + (f" -> {', '.join(p.references)}" if p.references else "")
            for p in self.project_layout
        )
        lines.append("")
        lines.append(f"Importance order for the structural map: {' > '.join(self.layer_order)}")
        return "\n".join(lines)


_TEMPLATES: Final[tuple[ArchitectureTemplate, ...]] = (
    ArchitectureTemplate(
        id="minimal-service",
        display_name="Minimal service",
        summary="Single project, minimal API, feature folders, EF Core, no mediator.",
        project_layout=(
            ProjectSpec(name="Api", kind="webapi", path="src/Api", layer="api"),
            ProjectSpec(name="Api.Tests", kind="xunit", path="tests/Api.Tests", layer="tests", references=("Api",)),
        ),
        layer_order=("api", "tests"),
        built_in_task="T023",
    ),
    ArchitectureTemplate(
        id="vertical-slice",
        display_name="Vertical slice",
        summary="Feature-folder slices, one handler per slice, EF Core.",
        project_layout=(
            ProjectSpec(name="Domain", kind="classlib", path="src/Domain", layer="domain"),
            ProjectSpec(name="Api", kind="webapi", path="src/Api", layer="api", references=("Domain",)),
            ProjectSpec(name="Api.Tests", kind="xunit", path="tests/Api.Tests", layer="tests", references=("Api", "Domain")),
        ),
        layer_order=("domain", "api", "tests"),
        built_in_task="T024",
        prune=("src/Domain/Class1.cs", "src/Api/Api.http", "tests/Api.Tests/UnitTest1.cs"),
    ),
    ArchitectureTemplate(
        id="clean-arch",
        display_name="Clean architecture",
        summary="Domain / Application / Infrastructure / Api layering with CQRS.",
        project_layout=(
            ProjectSpec(name="Domain", kind="classlib", path="src/Domain", layer="domain"),
            ProjectSpec(name="Application", kind="classlib", path="src/Application", layer="application", references=("Domain",)),
            ProjectSpec(name="Infrastructure", kind="classlib", path="src/Infrastructure", layer="infrastructure", references=("Application", "Domain")),
            ProjectSpec(name="Api", kind="webapi", path="src/Api", layer="api", references=("Application", "Infrastructure")),
            ProjectSpec(name="Api.Tests", kind="xunit", path="tests/Api.Tests", layer="tests", references=("Api", "Application", "Domain")),
        ),
        layer_order=("domain", "application", "infrastructure", "api", "tests"),
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
    """Resolve an id and assert its overlay exists, for callers about to scaffold from it."""
    template = get(template_id)
    if not template.is_built:
        raise TemplateNotBuiltError(template.id, template.built_in_task)
    return template
