# -*- coding: utf-8 -*-
"""Component registry + per-env-var help text + FileStatus dataclass.

A Component describes one source under `global/` that maps onto a destination
inside `~/.claude/`. The wizard iterates COMPONENTS during update / doctor /
restore flows; ENV_DESCRIPTIONS supplies the long-form help for env-var rows
on the Init Env screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cabal._paths import GLOBAL_DIR, TARGET
from cabal.os_filters import _os_should_skip, _is_plugin_only


@dataclass
class Component:
    key: str
    label: str
    type: str
    src: str
    dst: str
    glob: str = "*"
    recursive: bool = False

    @property
    def src_path(self) -> Path:
        return GLOBAL_DIR / self.src

    @property
    def dst_path(self) -> Path:
        return TARGET / self.dst

    def list_files(self) -> list[tuple[Path, Path]]:
        if not self.src_path.exists():
            return []
        if self.type == "file":
            if _os_should_skip(self.src_path.name) or _is_plugin_only(Path(self.src)):
                return []
            return [(self.src_path, Path(self.src).name)]
        out: list[tuple[Path, Path]] = []
        iterator = (
            self.src_path.rglob("*")
            if self.recursive
            else self.src_path.glob(self.glob)
        )
        for f in iterator:
            if not f.is_file() or _os_should_skip(f.name):
                continue
            rel = f.relative_to(self.src_path)
            if _is_plugin_only(Path(self.src) / rel):
                continue
            out.append((f, rel))
        return out


COMPONENTS: list[Component] = [
    Component("settings", "settings.json", "file", "settings.json", "settings.json"),
    Component("claude_md", "CLAUDE.md", "file", "CLAUDE.md", "CLAUDE.md"),
    Component("design_md", "DESIGN.md", "file", "DESIGN.md", "DESIGN.md"),
    Component(
        "keybindings",
        "keybindings.json",
        "file",
        "keybindings.json",
        "keybindings.json",
    ),
    Component("statusline", "statusline.py", "file", "statusline.py", "statusline.py"),
    Component(
        "statusline_segments",
        "statusline-segments.json",
        "file",
        "statusline-segments.json",
        "statusline-segments.json",
    ),
    Component("agents", "agents/", "dir", "agents", "agents", glob="*.md"),
    Component("hooks", "hooks/", "dir", "hooks", "hooks", glob="*"),
    Component("skills", "skills/", "dir", "skills", "skills", glob="*.md"),
    Component("rules", "rules/", "dir", "rules", "rules", glob="*.md"),
    Component(
        "output_styles",
        "output-styles/",
        "dir",
        "output-styles",
        "output-styles",
        glob="*.md",
    ),
    Component(
        "project_templates",
        "project-templates/",
        "dir",
        "project-templates",
        "project-templates",
        glob="*.md",
    ),
    Component("git_templates", "git/ templates", "dir", "git", "git", recursive=True),
]

ENV_DESCRIPTIONS: dict[str, str] = {
    "FIGMA_ACCESS_TOKEN": (
        "Figma MCP server — gives Claude read access to files, components, and design tokens. "
        "Create at figma.com/settings under Personal access tokens."
    ),
    "POSTGRES_CONNECTION_STRING": (
        "Direct PostgreSQL connection for services that query the DB (e.g. postgresql://user:pass@host:5432/db). "
        "Not required for MCP servers — only for local service scripts."
    ),
    "AZURE_DEVOPS_ORG_URL": (
        "Azure DevOps MCP server — your organisation URL (e.g. https://dev.azure.com/your-org). "
        "Pair with AZURE_DEVOPS_TOKEN."
    ),
    "AZURE_DEVOPS_TOKEN": (
        "Azure DevOps MCP server — Personal Access Token for work items, repos, pipelines, and PRs. "
        "Create in Azure DevOps → User Settings → Personal access tokens."
    ),
    "SUPABASE_ACCESS_TOKEN": (
        "Supabase MCP server — gives Claude access to your project's DB, auth, storage, and edge functions. "
        "Create at supabase.com/dashboard/account/tokens."
    ),
    "OBSIDIAN_API_KEY": (
        "Obsidian MCP server — API key from the Local REST API plugin. "
        "Lets Claude read and search your vault. Enable the plugin in Obsidian first."
    ),
    "OBSIDIAN_HOST": (
        "Obsidian MCP server — host where the Local REST API plugin listens (default: 127.0.0.1). "
        "Change only if Obsidian runs on a remote machine."
    ),
    "OBSIDIAN_PORT": (
        "Obsidian MCP server — port for the Local REST API plugin (default: 27123). "
        "Change only if you've set a custom port in the plugin settings."
    ),
    "PROJECTS_PATH": (
        "Base directory for your projects (e.g. C:/projects or ~/projects). "
        "Used by session hooks and helper scripts to resolve project paths."
    ),
    "TEMP_PATH": (
        "Scratch directory for temporary files generated during Claude sessions. "
        "Defaults to the OS temp dir if left empty."
    ),
    "GIT_LINE_ENDINGS": (
        "Sets git core.autocrlf globally. "
        "auto = LF in repo, CRLF on Windows checkout (recommended). "
        "Other values: true, false, input."
    ),
}


@dataclass
class FileStatus:
    rel: Path
    src: Path
    dst: Path
    state: str  # NEW | CHANGED | UNCHANGED
