# -*- coding: utf-8 -*-
"""Per-project state: the locked architecture template, the map fingerprint, and touched types.

The template is recorded once at project creation and is immutable for the project's lifetime
(FR-001a/b). Changing it is refused, not migrated (FR-001c).

That immutability is not bureaucracy — it is what makes the rules band of the prompt cacheable.
A tool that re-decided architecture per run would place a volatile value high in the prefix and
invalidate everything below it, so the architecture lock and the caching strategy are one
decision seen twice (research R5).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from cabal.dotnetgen.templates.registry import TEMPLATE_IDS

STATE_RELPATH: Final[str] = ".dotnetgen/state.json"
RECENT_TYPES_LIMIT: Final[int] = 32


class StateError(ValueError):
    """Raised when project state is missing, malformed, or would be illegally mutated."""


class TemplateLockError(StateError):
    """Raised on any attempt to change a project's recorded template."""


@dataclass(frozen=True)
class ProjectState:
    """Written once at creation; only the fingerprint and recency list ever change."""

    template_id: str
    created_at: str
    solution_path: str
    map_fingerprint: str | None = None
    recent_types: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "created_at": self.created_at,
            "solution_path": self.solution_path,
            "map_fingerprint": self.map_fingerprint,
            "recent_types": list(self.recent_types),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ProjectState":
        missing = [k for k in ("template_id", "created_at", "solution_path") if k not in payload]
        if missing:
            raise StateError(f"state file is missing {', '.join(missing)}")
        if payload["template_id"] not in TEMPLATE_IDS:
            raise StateError(
                f"state file records unknown template {payload['template_id']!r}; "
                f"expected one of {TEMPLATE_IDS}"
            )
        return cls(
            template_id=payload["template_id"],
            created_at=payload["created_at"],
            solution_path=payload["solution_path"],
            map_fingerprint=payload.get("map_fingerprint"),
            recent_types=tuple(payload.get("recent_types", ())),
        )


def state_path(project: Path) -> Path:
    return project / STATE_RELPATH


def exists(project: Path) -> bool:
    return state_path(project).is_file()


def load(project: Path) -> ProjectState:
    path = state_path(project)
    if not path.is_file():
        raise StateError(f"no project state at {path}; run `new` to create a project first")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateError(f"{path} is not valid JSON: {exc}") from exc
    return ProjectState.from_dict(payload)


def save(project: Path, state: ProjectState) -> ProjectState:
    """Persist state, refusing any write that would change the recorded template."""
    path = state_path(project)
    if path.is_file():
        current = load(project)
        if current.template_id != state.template_id:
            raise TemplateLockError(
                f"project template is locked to {current.template_id!r} and cannot become "
                f"{state.template_id!r}; changing template is out of scope - create a new project"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")
    return state


def create(project: Path, template_id: str) -> ProjectState:
    """Record the template choice. Refuses if the project already has state."""
    if template_id not in TEMPLATE_IDS:
        raise StateError(
            f"unknown template {template_id!r}; expected one of {TEMPLATE_IDS}. "
            "The set is closed - an unknown id is an error, never a fallback."
        )
    if exists(project):
        current = load(project)
        raise TemplateLockError(
            f"project already exists with template {current.template_id!r}; "
            "template choice is made once, at creation"
        )
    state = ProjectState(
        template_id=template_id,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        solution_path=str(project),
    )
    return save(project, state)


def assert_template(project: Path, requested: str) -> ProjectState:
    """Read the recorded template, refusing a request that names a different one."""
    state = load(project)
    if requested != state.template_id:
        raise TemplateLockError(
            f"project template is {state.template_id!r}, not {requested!r}; "
            "the recorded template is read, never re-decided"
        )
    return state


def structural_fingerprint(relative_paths_and_sizes: dict[str, int]) -> str:
    """Fingerprint a solution's shape, so an unchanged solution reuses its cached map byte-for-byte."""
    digest = hashlib.sha256()
    for path in sorted(relative_paths_and_sizes):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(relative_paths_and_sizes[path]).encode("utf-8"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def record_map(project: Path, fingerprint: str) -> ProjectState:
    return save(project, replace(load(project), map_fingerprint=fingerprint))


def touch_types(project: Path, type_names: tuple[str, ...]) -> ProjectState:
    """Move the given types to the front of the recency list, most recent first."""
    state = load(project)
    ordered = list(type_names) + [t for t in state.recent_types if t not in type_names]
    return save(project, replace(state, recent_types=tuple(ordered[:RECENT_TYPES_LIMIT])))
