# -*- coding: utf-8 -*-
"""Local project setup helpers for Codex assets."""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path
from typing import Any

from cabal.codex_setup.paths import CODEX_SOURCE_DIR

DRIFT_MARKUP = {
    "NEW": "[green]NEW - will add[/green]",
    "CHANGED": "[yellow]CHANGED - will update[/yellow]",
    "UNCHANGED": "[dim]installed (up to date)[/dim]",
}


def codex_project_status(project: Path) -> list[tuple[str, bool]]:
    agents = project / ".agents"
    return [
        ("AGENTS.md", (project / "AGENTS.md").exists()),
        (".agents/", agents.exists()),
        ("skills/", (agents / "skills").exists()),
    ]


def format_codex_project_status(project: Path) -> str:
    chips = [
        f"{'[green]OK[/green]' if present else '[red]--[/red]'} {label}"
        for label, present in codex_project_status(project)
    ]
    return "[bold]Codex project state:[/bold]  " + "   ".join(chips)


def _file_state(src: Path, dst: Path) -> str:
    if not dst.exists():
        return "NEW"
    try:
        return "UNCHANGED" if filecmp.cmp(src, dst, shallow=False) else "CHANGED"
    except OSError:
        return "CHANGED"


def _skill_children(project: Path) -> list[dict[str, Any]]:
    src_dir = CODEX_SOURCE_DIR / "skills"
    dst_dir = project / ".agents" / "skills"
    if not src_dir.exists():
        return [
            {
                "key": "skills::missing",
                "label": "global/codex/skills in repo",
                "state": "[red]MISSING[/red]",
                "op": None,
            }
        ]

    children: list[dict[str, Any]] = []
    global_names: set[str] = set()
    for src in sorted(p for p in src_dir.iterdir() if p.is_dir()):
        source_skill = src / "SKILL.md"
        if not source_skill.is_file():
            continue
        global_names.add(src.name)
        dst = dst_dir / src.name / "SKILL.md"
        state = _file_state(source_skill, dst)
        children.append(
            {
                "key": f"skills::{src.name}",
                "label": src.name,
                "state": DRIFT_MARKUP[state],
                "op": ("copy_tree", src, dst_dir / src.name)
                if state != "UNCHANGED"
                else None,
            }
        )

    if dst_dir.exists():
        for inst in sorted(p for p in dst_dir.iterdir() if p.is_dir()):
            if inst.name not in global_names:
                children.append(
                    {
                        "key": f"skills-local::{inst.name}",
                        "label": inst.name,
                        "state": "[blue]local-only (kept)[/blue]",
                        "op": None,
                    }
                )
    return children


def build_codex_local_plan(
    project: Path, selected: dict[str, bool], template: Path | None
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []

    if selected.get("scaffold"):
        kids: list[dict[str, Any]] = []
        for sub in [".agents", ".agents/skills"]:
            p = project / sub
            kids.append(
                {
                    "key": f"scaffold::{sub}",
                    "label": f"{sub}/",
                    "state": "[dim]exists (kept)[/dim]" if p.exists() else "[green]NEW[/green]",
                    "op": ("mkdir", p),
                }
            )
        groups.append({"action": "scaffold", "label": "scaffold", "children": kids})

    if selected.get("template"):
        if template is None:
            kids = [
                {
                    "key": "template::none",
                    "label": "AGENTS.md",
                    "state": "[yellow]Pick a template above[/yellow]",
                    "op": None,
                }
            ]
        else:
            target = project / "AGENTS.md"
            state = _file_state(template, target)
            kids = [
                {
                    "key": "template::AGENTS.md",
                    "label": f"AGENTS.md (from {template.stem})",
                    "state": DRIFT_MARKUP[state],
                    "op": ("copy", template, target) if state != "UNCHANGED" else None,
                }
            ]
        groups.append({"action": "template", "label": "AGENTS.md template", "children": kids})

    if selected.get("skills"):
        groups.append(
            {
                "action": "skills",
                "label": "Skills (global/codex/skills -> .agents/skills)",
                "children": _skill_children(project),
            }
        )

    return groups


def apply_codex_local_group(action: str, chosen: list[dict[str, Any]]) -> list[str]:
    actionable = [child for child in chosen if child.get("op") is not None]
    if not actionable:
        return []

    if action == "scaffold":
        for ch in actionable:
            _, target = ch["op"]
            target.mkdir(parents=True, exist_ok=True)
        return ["[green]OK Created .agents/ scaffold[/green]"]

    if action == "template":
        _, src, dst = actionable[0]["op"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return [f"[green]OK Wrote AGENTS.md from {src.stem}[/green]"]

    if action == "skills":
        count = 0
        for ch in actionable:
            _, src, dst = ch["op"]
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            count += 1
        return [f"[green]OK Synced {count} Codex skill(s) -> .agents/skills[/green]"]

    return []
