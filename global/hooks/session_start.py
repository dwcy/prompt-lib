#!/usr/bin/env python3
"""SessionStart hook — detect project state and inject context for Claude.

Cross-platform (Windows / Linux / macOS). Emits JSON with `additionalContext`
on stdout so Claude knows what to do at session start. Never fails the session:
any error exits 0 with no output.
"""
import json
import sys
from pathlib import Path


def emit(message: str) -> None:
    print(json.dumps({"additionalContext": message}))


def main() -> None:
    cwd = Path.cwd()

    if not (cwd / "CLAUDE.md").exists():
        emit(
            f"No CLAUDE.md was found in this project directory ({cwd}). Before doing "
            "anything else, ask the user whether they want to describe the project now "
            "so a CLAUDE.md can be created, or be reminded next session. If they "
            "describe it, create a CLAUDE.md at the project root with: a project name "
            "heading, what the project does, the tech stack, key directories, and any "
            "important workflows. If they decline, proceed normally without creating it."
        )
        return

    hints: list[str] = []

    if list(cwd.glob("*.sln")) or any(cwd.glob(f"{'*/' * d}*.csproj") for d in range(4)):
        hints.append(".NET")

    if (cwd / "requirements.txt").exists() or (cwd / "pyproject.toml").exists() or (cwd / "Pipfile").exists():
        hints.append("Python")

    pkg = cwd / "package.json"
    if pkg.exists():
        try:
            pkg_text = pkg.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pkg_text = ""
        is_monorepo = (
            '"workspaces"' in pkg_text
            or (cwd / "pnpm-workspace.yaml").exists()
            or (cwd / "turbo.json").exists()
            or (cwd / "nx.json").exists()
            or (cwd / "lerna.json").exists()
        )
        hints.append("Monorepo" if is_monorepo else "JavaScript/TypeScript")

    if (cwd / "Assets").exists() and (cwd / "ProjectSettings").exists():
        hints.append("Unity3D")

    stack = " + ".join(hints) if hints else "unknown stack"
    emit(
        f"Existing project detected ({stack}) in {cwd}. A CLAUDE.md exists. "
        "Proactively invoke the @load-project agent to read the project context and "
        "announce which specialist subagents are available for this session."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
