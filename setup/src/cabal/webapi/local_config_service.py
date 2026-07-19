# -*- coding: utf-8 -*-
"""Read model for the Local Project Config module: the scaffolding actions with per-item
previews and the template options that drive them. Wraps cabal.local_setup.build_plan;
the apply mutation lives in the action registry. `plan_to_actions` is shared with the
codex local-scaffold service since both build the same group/child plan shape."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from cabal._paths import GLOBAL_DIR
from cabal.gitignore_templates import GITIGNORE_BY_TEMPLATE
from cabal.local_setup import build_plan

_MARKUP_RE = re.compile(r"\[/?[a-z0-9 #]+\]", re.IGNORECASE)


def strip_rich_markup(text: str) -> str:
    """Drop Rich console markup tags so apply-status lines read cleanly in a job stream."""
    return _MARKUP_RE.sub("", text)

# Every scaffolding action the read model enumerates (build_plan only emits a group when its
# selector is truthy, so we ask for all of them and report applicability per group).
_ALL_LOCAL_ACTIONS = {
    "scaffold": True,
    "template": True,
    "gitignore": True,
    "git": True,
    "speckit": True,
    "skills": True,
}

_TEMPLATE_DIR = GLOBAL_DIR / "project-templates"


def _preview_state(markup: str, has_op: bool) -> str:
    """Collapse a build_plan child's Rich-markup drift label to a wire state.

    build_plan encodes state as display markup (local_setup.DRIFT_MARKUP + inline literals);
    the wire contract only distinguishes new / changed / skip (no-op or informational).
    """
    if not has_op:
        return "skip"
    lowered = markup.lower()
    if "new" in lowered:
        return "new"
    if any(keyword in lowered for keyword in ("kept", "up to date", "installed", "local-only")):
        return "skip"
    if any(keyword in lowered for keyword in ("append", "overwrite", "update", "changed", "force", "will run", "exists")):
        return "changed"
    return "skip"


def _child_to_item(child: dict[str, Any]) -> dict[str, Any]:
    state = _preview_state(str(child.get("state", "")), child.get("op") is not None)
    return {
        "key": child["key"],
        "rel_path": child["label"],
        "state": state,
        "selected": state in ("new", "changed"),
    }


def plan_to_actions(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map build_plan groups to the wire action list with clean per-item previews."""
    actions: list[dict[str, Any]] = []
    for group in groups:
        items = [_child_to_item(child) for child in group["children"]]
        pending = sum(1 for item in items if item["state"] in ("new", "changed"))
        actions.append(
            {
                "key": group["action"],
                "label": group["label"],
                "applicable": pending > 0,
                "applied_state": f"{pending} pending" if pending else "up to date",
                "preview_items": items,
            }
        )
    return actions


def _template_options() -> list[dict[str, str]]:
    if not _TEMPLATE_DIR.exists():
        return []
    return [{"value": path.stem, "label": path.stem} for path in sorted(_TEMPLATE_DIR.glob("*.md"))]


def _resolve_template(template_stem: str | None) -> Path | None:
    if not template_stem:
        return None
    candidate = _TEMPLATE_DIR / f"{template_stem}.md"
    return candidate if candidate.exists() else None


def local_plan(
    project: Path, *, template_stem: str | None = None, gitignore_stem: str | None = None
) -> list[dict[str, Any]]:
    """Raw build_plan groups for the enabled local-setup actions (shared with the apply action)."""
    gitignore_path = Path(gitignore_stem) if gitignore_stem else None
    return build_plan(project, _ALL_LOCAL_ACTIONS, _resolve_template(template_stem), gitignore_path)


def local_config_actions(
    project: Path | None, *, template_stem: str | None = None, gitignore_stem: str | None = None
) -> dict[str, Any]:
    """`/api/local-config` data: scaffolding actions + preview items + selectable options."""
    template_options = _template_options()
    gitignore_options = sorted(GITIGNORE_BY_TEMPLATE)
    if project is None:
        return {
            "actions": [],
            "template_options": template_options,
            "gitignore_options": gitignore_options,
            "project_selected": False,
        }
    groups = local_plan(project, template_stem=template_stem, gitignore_stem=gitignore_stem)
    return {
        "actions": plan_to_actions(groups),
        "template_options": template_options,
        "gitignore_options": gitignore_options,
        "project_selected": True,
    }
