# -*- coding: utf-8 -*-
"""Greenfield scaffolding: turn a locked template into a solution that already builds.

FR-003 is the point of this module. The first model turn must *edit a working solution*, not
create one from an empty directory - that is the single largest cost lever in the feature
(Principle E, scope deletion). So the scaffold runs `dotnet new`, applies the template's
convention overlay, and then **proves the result builds before any model is invited to touch
it**. A scaffold that produced a non-building skeleton would hand the model a repair job as its
opening move, which is precisely the waste the design exists to remove.

Nothing here calls a model. The whole greenfield skeleton costs zero tokens (SC-012).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cabal.dotnetgen import state
from cabal.dotnetgen.templates import registry
from cabal.dotnetgen.verify import dotnet


BUILD_ARTIFACT_DIRS: Final[tuple[str, ...]] = ("obj", "bin")
"""Never copied into a scaffold.

They are gitignored, so they never reach a clone - but `dotnet format` (run by the
`format_on_write` hook) restores in place, so they do appear in a working tree and would
otherwise be copied into every generated solution as stale artifacts from another machine.
"""


def _is_build_artifact(relpath: Path) -> bool:
    return any(part in BUILD_ARTIFACT_DIRS for part in relpath.parts)


class ScaffoldError(RuntimeError):
    """Raised when a scaffold step fails. Carries the failing command's output."""

    def __init__(self, message: str, output: dotnet.CommandOutput | None = None) -> None:
        super().__init__(message)
        self.output = output


@dataclass(frozen=True)
class ScaffoldPlan:
    """What a scaffold would do, computed without touching the filesystem."""

    template: registry.ArchitectureTemplate
    solution_name: str
    target: Path

    @property
    def steps(self) -> tuple[tuple[str, ...], ...]:
        return self.template.scaffold_steps(self.solution_name)

    @property
    def overlay_files(self) -> tuple[str, ...]:
        root = self.template.overlay_root
        return tuple(
            sorted(
                p.relative_to(root).as_posix()
                for p in root.rglob("*")
                if p.is_file() and not _is_build_artifact(p.relative_to(root))
            )
        )

    def describe(self) -> dict[str, object]:
        """The `--json` shape for `new`, and the human summary's source."""
        return {
            "status": "planned",
            "template": self.template.id,
            "display_name": self.template.display_name,
            "solution": self.solution_name,
            "target": str(self.target),
            "projects": [
                {"name": p.name, "path": p.path, "layer": p.layer, "references": list(p.references)}
                for p in self.template.project_layout
            ],
            "scaffold_command": self.template.scaffold_command,
            "overlay_files": list(self.overlay_files),
            "pruned_files": list(self.template.prune),
            "conventions_digest": self.template.conventions_digest,
        }


@dataclass(frozen=True)
class ScaffoldResult:
    """A completed scaffold, including the build that proves FR-003 held."""

    plan: ScaffoldPlan
    build: dotnet.CommandOutput
    project_state: state.ProjectState

    def describe(self) -> dict[str, object]:
        return {
            **self.plan.describe(),
            "status": "created",
            "builds": self.build.ok,
            "created_at": self.project_state.created_at,
        }


def plan(target: Path, template_id: str, solution_name: str | None = None) -> ScaffoldPlan:
    """Resolve the template and compute the recipe. Refuses an unbuilt or unknown template."""
    template = registry.require_built(template_id)
    resolved = target.resolve()
    return ScaffoldPlan(
        template=template,
        solution_name=solution_name or _solution_name_from(resolved),
        target=resolved,
    )


def execute(scaffold_plan: ScaffoldPlan) -> ScaffoldResult:
    """Run the recipe, apply the overlay, record state, and verify the result builds."""
    target = scaffold_plan.target
    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()):
        raise ScaffoldError(
            f"{target} is not empty; `new` scaffolds into an empty directory so that nothing "
            "existing is silently overwritten"
        )

    for step in scaffold_plan.steps:
        output = dotnet.run_command(step, cwd=target, timeout=dotnet.BUILD_TIMEOUT_SECONDS)
        if not output.ok:
            raise ScaffoldError(f"scaffold step failed: dotnet {' '.join(step)}", output)

    _prune(target, scaffold_plan.template.prune)
    shutil.copytree(
        scaffold_plan.template.overlay_root,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*BUILD_ARTIFACT_DIRS),
    )

    project_state = state.create(target, scaffold_plan.template.id)

    build = dotnet.build(target)
    if not build.ok:
        raise ScaffoldError(
            "the scaffolded solution does not build - FR-003 requires a runnable skeleton "
            "before any model writes to it, so this is a template defect, not a code defect",
            build,
        )
    return ScaffoldResult(plan=scaffold_plan, build=build, project_state=project_state)


def _prune(target: Path, relpaths: tuple[str, ...]) -> None:
    """Remove the sample files `dotnet new` emits that the overlay does not want."""
    for relpath in relpaths:
        (target / relpath).unlink(missing_ok=True)


def _solution_name_from(target: Path) -> str:
    """Name the solution after its directory, falling back when that is not a usable identifier."""
    candidate = "".join(ch for ch in target.name if ch.isalnum() or ch in "._-").strip("._-")
    return candidate or "Service"
