# -*- coding: utf-8 -*-
"""Read models unique to the Codex Parity module: the conversion audit (repo asset -> Codex
output state) and the Codex local-scaffold plan. The Codex deploy tree / diff / extras reuse
config_service with target="codex"; mutations live in the action registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cabal.codex_setup.conversion import audit_conversion_entries
from cabal.codex_setup.local_setup import build_codex_local_plan
from cabal.codex_setup.paths import CODEX_SOURCE_DIR
from cabal.webapi.local_config_service import plan_to_actions

_ALL_CODEX_LOCAL_ACTIONS = {"scaffold": True, "template": True, "skills": True}
_CODEX_TEMPLATE_DIR = CODEX_SOURCE_DIR / "project-templates"


def codex_conversion() -> dict[str, Any]:
    """`/api/codex/conversion` data: per-asset conversion audit with source/output comparison."""
    rows = []
    for entry in audit_conversion_entries():
        asset = entry.source_label if entry.source is not None else entry.output_label
        rows.append(
            {
                "asset": asset,
                "state": entry.status,
                "kind": entry.kind,
                "source_path": entry.source_label,
                "output_path": entry.output_label,
                "reason": entry.reason,
            }
        )
    return {"rows": rows}


def _codex_template_options() -> list[dict[str, str]]:
    if not _CODEX_TEMPLATE_DIR.exists():
        return []
    return [{"value": path.stem, "label": path.stem} for path in sorted(_CODEX_TEMPLATE_DIR.glob("*.md"))]


def _resolve_codex_template(template_stem: str | None) -> Path | None:
    if not template_stem:
        return None
    candidate = _CODEX_TEMPLATE_DIR / f"{template_stem}.md"
    return candidate if candidate.exists() else None


def codex_local_actions(project: Path | None, *, template_stem: str | None = None) -> dict[str, Any]:
    """`/api/codex/local-config` data: Codex scaffolding actions + preview items + options."""
    if project is None:
        return {"actions": [], "template_options": _codex_template_options(), "project_selected": False}
    groups = build_codex_local_plan(project, _ALL_CODEX_LOCAL_ACTIONS, _resolve_codex_template(template_stem))
    return {
        "actions": plan_to_actions(groups),
        "template_options": _codex_template_options(),
        "project_selected": True,
    }
