# -*- coding: utf-8 -*-
"""Prompt template for the post-Apply `claude -p` invocation. Persisted at <target>/.claude/INIT_PROMPT.md."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def build_init_prompt(
    target_dir: Path,
    template_attribution: str,
    files_written: Iterable[str],
    agents: Iterable[str],
    skills: Iterable[str],
    commands: Iterable[str],
) -> str:
    """Render the INIT_PROMPT.md body for the new project."""
    files_block = "\n".join(f"- {f}" for f in sorted(files_written)) or "(none)"
    agents_block = "\n".join(f"- @{a}" for a in sorted(agents)) or "(none discovered under .claude/agents/)"
    skills_block = "\n".join(f"- /{s}" for s in sorted(skills)) or "(none discovered under .claude/skills/)"
    cmds_block = "\n".join(f"- /{c}" for c in sorted(commands)) or "(none discovered under .claude/commands/)"
    return (
        f"# Init Project Prompt\n\n"
        f"You are inside a brand-new project at `{target_dir}` that was just scaffolded by cabal.\n\n"
        f"## Template\n\n"
        f"{template_attribution}\n\n"
        f"## Files written by the wizard\n\n"
        f"{files_block}\n\n"
        f"## Agents now available\n\n"
        f"{agents_block}\n\n"
        f"## Skills now available\n\n"
        f"{skills_block}\n\n"
        f"## Commands now available\n\n"
        f"{cmds_block}\n\n"
        f"## Your task\n\n"
        f"Follow the architecture template above and finish setting up `{target_dir.name}` against the files in `.claude/`. "
        f"Start by acknowledging the template and outlining what you will do.\n"
    )


def write_init_prompt(target_dir: Path, prompt_text: str) -> Path:
    """Write the prompt to `<target>/.claude/INIT_PROMPT.md` and return its path."""
    out = target_dir / ".claude" / "INIT_PROMPT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(prompt_text, encoding="utf-8")
    return out
