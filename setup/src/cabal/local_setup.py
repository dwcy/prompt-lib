# -*- coding: utf-8 -*-
"""Plan builder + file/git apply logic for LocalScreen (keeps the view thin).

`build_plan` groups the enabled local-setup actions into parent/child nodes the
screen renders and selects against; `apply_group` executes the selected children
for the file-based actions (scaffold / template / gitignore / git). Spec Kit stays
in the screen because it needs the Textual app's `suspend()`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from cabal._paths import GLOBAL_DIR
from cabal.views.folder_browser import GITIGNORE_BY_TEMPLATE

SETTINGS_LOCAL_STUB = '{\n  "permissions": {\n    "allow": []\n  }\n}\n'


def _state(exists: bool, *, append: bool = False) -> str:
    if not exists:
        return "[green]NEW[/green]"
    if append:
        return "[yellow]EXISTS — will APPEND[/yellow]"
    return "[yellow]EXISTS — would OVERWRITE[/yellow]"


def build_plan(
    project: Path, sel: dict[str, bool], tpl: Path | None, picked: Path | None
) -> list[dict[str, Any]]:
    """Ordered groups: {action, label, children:[{key,label,state,op}]}.

    `op` is None for informational rows (not selectable, nothing to apply).
    """
    groups: list[dict[str, Any]] = []

    if sel.get("scaffold"):
        kids: list[dict[str, Any]] = []
        for sub in [".claude", ".claude/skills", ".claude/hooks"]:
            p = project / sub
            kids.append(
                {
                    "key": f"scaffold::{sub}",
                    "label": f"{sub}/",
                    "state": "[dim]exists (kept)[/dim]"
                    if p.exists()
                    else "[green]NEW[/green]",
                    "op": ("mkdir", p),
                }
            )
        sl = project / ".claude" / "settings.local.json"
        kids.append(
            {
                "key": "scaffold::settings.local.json",
                "label": ".claude/settings.local.json",
                "state": "[dim]exists (kept)[/dim]"
                if sl.exists()
                else "[green]NEW[/green]",
                "op": ("settings_local", sl),
            }
        )
        groups.append({"action": "scaffold", "label": "scaffold", "children": kids})

    if sel.get("template"):
        if tpl:
            target = project / "CLAUDE.md"
            kids = [
                {
                    "key": "template::CLAUDE.md",
                    "label": f"CLAUDE.md  (from {tpl.stem})",
                    "state": _state(target.exists()),
                    "op": ("copy", tpl, target),
                }
            ]
        else:
            kids = [
                {
                    "key": "template::none",
                    "label": "—",
                    "state": "[yellow]Pick a template above[/yellow]",
                    "op": None,
                }
            ]
        groups.append(
            {"action": "template", "label": "CLAUDE.md template", "children": kids}
        )

    if sel.get("gitignore"):
        if picked is None:
            kids = [
                {
                    "key": "gitignore::none",
                    "label": ".gitignore",
                    "state": "[yellow]Pick a template above[/yellow]",
                    "op": None,
                }
            ]
        elif picked.stem not in GITIGNORE_BY_TEMPLATE:
            kids = [
                {
                    "key": "gitignore::nopreset",
                    "label": ".gitignore",
                    "state": f"[yellow]no preset for '{picked.stem}'[/yellow]",
                    "op": None,
                }
            ]
        else:
            target = project / ".gitignore"
            kids = [
                {
                    "key": "gitignore::.gitignore",
                    "label": f".gitignore  ({picked.stem} preset)",
                    "state": _state(target.exists(), append=True),
                    "op": ("gitignore", picked.stem, target),
                }
            ]
        groups.append({"action": "gitignore", "label": ".gitignore", "children": kids})

    if sel.get("git"):
        git_src = GLOBAL_DIR / "git"
        git_dir = project / ".git"
        kids = []
        if not git_src.exists():
            kids.append(
                {
                    "key": "git::missing",
                    "label": "global/git/ in repo",
                    "state": "[red]MISSING[/red]",
                    "op": None,
                }
            )
        else:
            hooks_src = git_src / "hooks"
            if hooks_src.exists():
                for f in sorted(hooks_src.iterdir()):
                    if f.is_file():
                        target = git_dir / "hooks" / f.name
                        state = _state(git_dir.exists() and target.exists())
                        kids.append(
                            {
                                "key": f"git::hooks/{f.name}",
                                "label": f".git/hooks/{f.name}",
                                "state": state,
                                "op": ("copy", f, target),
                            }
                        )
            for f in sorted(git_src.iterdir()):
                if f.is_file():
                    target = project / f.name
                    kids.append(
                        {
                            "key": f"git::{f.name}",
                            "label": f.name,
                            "state": _state(target.exists()),
                            "op": ("copy", f, target),
                        }
                    )
        label = "git repo-init" + (
            " [dim](will run git init)[/dim]" if not git_dir.exists() else ""
        )
        groups.append({"action": "git", "label": label, "children": kids})

    if sel.get("speckit"):
        if not shutil.which("specify"):
            kids = [
                {
                    "key": "speckit::missing",
                    "label": "specify CLI",
                    "state": "[red]not installed — see Tools screen[/red]",
                    "op": None,
                }
            ]
        else:
            exists = (project / ".specify").exists()
            state = (
                "[yellow]EXISTS — will run with --force[/yellow]"
                if exists
                else "[green]NEW (specify init --here --integration claude)[/green]"
            )
            kids = [
                {
                    "key": "speckit::.specify",
                    "label": ".specify/",
                    "state": state,
                    "op": ("speckit", project),
                }
            ]
        groups.append({"action": "speckit", "label": "Spec Kit", "children": kids})

    return groups


def apply_group(action: str, chosen: list[dict[str, Any]], project: Path) -> list[str]:
    """Execute selected children for a file-based action; return status message lines."""
    if action == "scaffold":
        for ch in chosen:
            kind, target = ch["op"][0], ch["op"][1]
            if kind == "mkdir":
                target.mkdir(parents=True, exist_ok=True)
            elif kind == "settings_local" and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(SETTINGS_LOCAL_STUB, encoding="utf-8")
        return [
            "[green]✓ Created .claude/ scaffold[/green]\n"
            "  Verify: ls .claude/ → selected dirs + settings.local.json\n"
            "  [yellow]⚑ TODO: edit .claude/settings.local.json — add allow[] entries for this project's commands.[/yellow]"
        ]

    if action == "template":
        _, src, dst = chosen[0]["op"]
        shutil.copy2(src, dst)
        return [
            f"[green]✓ Wrote CLAUDE.md from {src.stem}[/green]\n"
            "  Verify: open a new Claude Code session here — SessionStart hook should invoke @load-project."
        ]

    if action == "gitignore":
        _, stem, target = chosen[0]["op"]
        ignore_text = GITIGNORE_BY_TEMPLATE.get(stem, "")
        header = f"# Added by cabal wizard ({stem} preset)\n"
        if target.exists():
            combined = (
                target.read_text(encoding="utf-8").rstrip()
                + "\n\n"
                + header
                + ignore_text
            )
            target.write_text(combined, encoding="utf-8")
            return [
                f"[green]✓ Appended .gitignore ({stem} preset)[/green]\n  Verify: cat .gitignore → new {stem} block at the bottom."
            ]
        target.write_text(header + ignore_text, encoding="utf-8")
        return [
            f"[green]✓ Wrote .gitignore ({stem} preset)[/green]\n  Verify: cat .gitignore → stack-specific ignore rules present."
        ]

    if action == "git":
        git_dir = project / ".git"
        if not git_dir.exists():
            if not shutil.which("git"):
                return ["[red]✗ git not found on PATH — cannot run git init[/red]"]
            r = subprocess.run(
                ["git", "init", str(project)], capture_output=True, text=True
            )
            if r.returncode != 0:
                return [f"[red]✗ git init failed:[/red] {r.stderr.strip()}"]
        for ch in chosen:
            _, src, dst = ch["op"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return [
            f"[green]✓ Applied git repo-init template[/green] ({len(chosen)} files)\n"
            "  [yellow]⚑ TODO (Unix only): chmod +x .git/hooks/* — execute bit not preserved on Windows copy.[/yellow]"
        ]

    return []
