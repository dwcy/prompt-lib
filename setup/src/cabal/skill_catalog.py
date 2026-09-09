# -*- coding: utf-8 -*-
"""Discovery of the skills Claude Code actually loads for a machine + project: personal
(~/.claude/skills, ~/.claude/commands), project (.claude/skills, .claude/commands) and
installed-plugin skills and commands, each with its parsed frontmatter."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from cabal._paths import TARGET

SKILL_FILENAME = "SKILL.md"
MAX_BUNDLED_SCAN = 500

# A loose .md directly under skills/ is silently ignored by Claude Code — only a folder with a
# SKILL.md inside is loaded. Surfacing it is the whole point of listing it at all.
LOOSE_FILE_REASON = (
    "A skill has to be a folder with a SKILL.md inside it. A loose .md file directly under "
    "skills/ is ignored — move it to <name>/SKILL.md to make it load."
)
DISABLED_PLUGIN_REASON = "Its plugin is installed but switched off in settings.json enabledPlugins."


@dataclass(frozen=True)
class SkillRecord:
    """One skill or command definition found on disk."""

    id: str
    name: str
    invocation: str
    scope: str  # "user" | "project" | "plugin"
    kind: str  # "skill" | "command"
    path: Path
    dir_path: Path | None
    description: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    plugin: str | None = None
    marketplace: str | None = None
    plugin_enabled: bool | None = None
    loaded: bool = True
    not_loaded_reason: str | None = None

    @property
    def allowed_tools(self) -> tuple[str, ...]:
        return as_list(self.frontmatter.get("allowed-tools") or self.frontmatter.get("tools"))

    @property
    def model(self) -> str | None:
        value = self.frontmatter.get("model")
        return str(value) if isinstance(value, (str, int)) else None

    @property
    def argument_hint(self) -> str | None:
        value = self.frontmatter.get("argument-hint")
        return str(value) if isinstance(value, str) else None


def as_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip().strip("[]")
    if not text:
        return ()
    return tuple(part.strip() for part in text.split(",") if part.strip())


# -- frontmatter ---------------------------------------------------------


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body) for a `---` delimited markdown file."""
    stripped = text.lstrip("﻿")
    if not stripped.startswith("---"):
        return "", stripped
    newline = stripped.find("\n")
    if newline == -1:
        return "", stripped
    end = stripped.find("\n---", newline)
    if end == -1:
        return "", stripped
    block = stripped[newline + 1 : end]
    rest = stripped[end + 4 :]
    return block, rest.lstrip("\r\n")


def _scalar(raw: str) -> Any:
    value = raw.strip()
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        return [part.strip().strip("\"'") for part in value[1:-1].split(",") if part.strip()]
    return value


def parse_frontmatter(block: str) -> dict[str, Any]:
    """Parse the YAML subset skills use: inline scalars, inline/block lists, block scalars.

    An indented nested mapping (`metadata:` with children) is read as an empty list rather than
    swallowing the keys that follow it — no skill field the UI shows is nested.
    """
    result: dict[str, Any] = {}
    lines = block.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.strip() or line.startswith(("#", " ", "\t")):
            continue
        key, separator, raw = line.partition(":")
        if not separator:
            continue
        key = key.strip()
        raw = raw.strip()
        if raw in (">", "|", ">-", "|-", ">+", "|+"):
            result[key], index = _read_block_scalar(lines, index, fold=raw[0] == ">")
        elif raw == "":
            result[key], index = _read_block_list(lines, index)
        else:
            result[key] = _scalar(raw)
    return result


def _read_block_scalar(lines: list[str], index: int, *, fold: bool) -> tuple[str, int]:
    collected: list[str] = []
    while index < len(lines):
        line = lines[index]
        if line.strip() and not line.startswith((" ", "\t")):
            break
        collected.append(line.strip())
        index += 1
    joiner = " " if fold else "\n"
    return joiner.join(collected).strip(), index


def _read_block_list(lines: list[str], index: int) -> tuple[list[str], int]:
    items: list[str] = []
    while index < len(lines):
        line = lines[index]
        if line.strip() and not line.startswith((" ", "\t")):
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(str(_scalar(stripped[2:])))
        index += 1
    return items, index


def read_definition(path: Path) -> tuple[dict[str, Any], str]:
    """Return (frontmatter, body) for one skill/command markdown file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}, ""
    block, body = split_frontmatter(text)
    return parse_frontmatter(block), body


def iso_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def count_bundled(skill_dir: Path) -> int:
    """Files the skill folder ships alongside SKILL.md (references/, scripts/, assets/, ...)."""
    total = 0
    try:
        for child in skill_dir.rglob("*"):
            if child.is_file() and child.name != SKILL_FILENAME:
                total += 1
                if total >= MAX_BUNDLED_SCAN:
                    break
    except OSError:
        return total
    return total


# -- discovery -----------------------------------------------------------


def _description(frontmatter: dict[str, Any]) -> str:
    value = frontmatter.get("description")
    return str(value).strip() if isinstance(value, (str, int)) else ""


def _record(
    *,
    name: str,
    invocation: str,
    scope: str,
    kind: str,
    path: Path,
    dir_path: Path | None,
    plugin: str | None = None,
    marketplace: str | None = None,
    plugin_enabled: bool | None = None,
    loaded: bool = True,
    not_loaded_reason: str | None = None,
) -> SkillRecord:
    frontmatter, _ = read_definition(path)
    qualifier = f"{plugin}/{name}" if plugin else name
    return SkillRecord(
        id=f"{scope}:{kind}:{qualifier}",
        name=name,
        invocation=invocation,
        scope=scope,
        kind=kind,
        path=path,
        dir_path=dir_path,
        description=_description(frontmatter),
        frontmatter=frontmatter,
        plugin=plugin,
        marketplace=marketplace,
        plugin_enabled=plugin_enabled,
        loaded=loaded,
        not_loaded_reason=not_loaded_reason,
    )


def _skills_in(skills_dir: Path, scope: str) -> list[SkillRecord]:
    if not skills_dir.is_dir():
        return []
    records: list[SkillRecord] = []
    for child in sorted(skills_dir.iterdir(), key=lambda item: item.name.lower()):
        if child.is_dir():
            definition = child / SKILL_FILENAME
            if definition.is_file():
                records.append(
                    _record(
                        name=child.name,
                        invocation=f"/{child.name}",
                        scope=scope,
                        kind="skill",
                        path=definition,
                        dir_path=child,
                    )
                )
        elif child.suffix.lower() == ".md":
            records.append(
                _record(
                    name=child.stem,
                    invocation=f"/{child.stem}",
                    scope=scope,
                    kind="skill",
                    path=child,
                    dir_path=None,
                    loaded=False,
                    not_loaded_reason=LOOSE_FILE_REASON,
                )
            )
    return records


def _commands_in(commands_dir: Path, scope: str) -> list[SkillRecord]:
    if not commands_dir.is_dir():
        return []
    records: list[SkillRecord] = []
    for path in sorted(commands_dir.rglob("*.md"), key=lambda item: item.as_posix().lower()):
        if not path.is_file():
            continue
        relative = path.relative_to(commands_dir).with_suffix("")
        name = ":".join(relative.parts)
        records.append(
            _record(
                name=name,
                invocation=f"/{name}",
                scope=scope,
                kind="command",
                path=path,
                dir_path=None,
            )
        )
    return records


def _enabled_plugins(claude_home: Path) -> dict[str, bool]:
    try:
        payload = json.loads((claude_home / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    flags = payload.get("enabledPlugins")
    if not isinstance(flags, dict):
        return {}
    return {str(key): bool(value) for key, value in flags.items()}


def _installed_plugins(claude_home: Path, project: Path | None) -> list[dict[str, Any]]:
    """One entry per installed plugin that applies here.

    `installed_plugins.json` records a plugin once per install scope; a project-scoped install
    only applies to that project path, so a project entry beats a user entry when it matches.
    """
    manifest = claude_home / "plugins" / "installed_plugins.json"
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    enabled = _enabled_plugins(claude_home)
    project_resolved = project.resolve() if project is not None else None

    chosen: list[dict[str, Any]] = []
    for key, installs in (payload.get("plugins") or {}).items():
        if not isinstance(installs, list):
            continue
        plugin, _, marketplace = str(key).partition("@")
        user_install: dict[str, Any] | None = None
        project_install: dict[str, Any] | None = None
        for install in installs:
            if not isinstance(install, dict):
                continue
            if install.get("scope") == "user":
                user_install = user_install or install
            elif install.get("scope") == "project" and project_resolved is not None:
                recorded = install.get("projectPath")
                if isinstance(recorded, str) and Path(recorded).resolve() == project_resolved:
                    project_install = install
        install = project_install or user_install
        if install is None or not isinstance(install.get("installPath"), str):
            continue
        version = install.get("version")
        root = Path(str(install["installPath"]))
        chosen.append(
            {
                # The `/plugin:skill` namespace comes from plugin.json's own name, which can
                # differ from the marketplace's folder name (vercel-plugin ships as `vercel`).
                "plugin": _plugin_manifest_name(root) or plugin,
                "marketplace": marketplace or None,
                "root": root,
                "version": str(version) if isinstance(version, str) else None,
                "enabled": enabled.get(str(key), True),
            }
        )
    return sorted(chosen, key=lambda item: str(item["plugin"]).lower())


def _plugin_manifest_name(root: Path) -> str | None:
    try:
        payload = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    name = payload.get("name")
    return str(name) if isinstance(name, str) and name else None


def _plugin_records(entry: dict[str, Any]) -> list[SkillRecord]:
    plugin = str(entry["plugin"])
    root = Path(entry["root"])
    enabled = bool(entry["enabled"])
    shared: dict[str, Any] = {
        "scope": "plugin",
        "plugin": plugin,
        "marketplace": entry["marketplace"],
        "plugin_enabled": enabled,
        "loaded": enabled,
        "not_loaded_reason": None if enabled else DISABLED_PLUGIN_REASON,
    }
    records: list[SkillRecord] = []
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir(), key=lambda item: item.name.lower()):
            definition = child / SKILL_FILENAME
            if child.is_dir() and definition.is_file():
                records.append(
                    _record(
                        name=child.name,
                        invocation=f"/{plugin}:{child.name}",
                        kind="skill",
                        path=definition,
                        dir_path=child,
                        **shared,
                    )
                )
    commands_dir = root / "commands"
    if commands_dir.is_dir():
        for path in sorted(commands_dir.glob("*.md"), key=lambda item: item.name.lower()):
            if path.is_file() and not path.name.startswith("_"):
                records.append(
                    _record(
                        name=path.stem,
                        invocation=f"/{plugin}:{path.stem}",
                        kind="command",
                        path=path,
                        dir_path=None,
                        **shared,
                    )
                )
    return records


@dataclass(frozen=True)
class SkillSource:
    """One folder the catalog looked in, listed whether or not it held anything."""

    key: str
    label: str
    scope: str
    path: Path
    exists: bool
    count: int
    plugin_version: str | None = None
    plugin_enabled: bool | None = None


_Collector = Callable[[Path, str], list[SkillRecord]]


def discover_skills(
    project: Path | None = None,
    *,
    claude_home: Path = TARGET,
) -> tuple[tuple[SkillRecord, ...], tuple[SkillSource, ...]]:
    """Every skill/command definition reachable for `project`, plus the folders searched."""
    records: list[SkillRecord] = []
    sources: list[SkillSource] = []

    lookups: list[tuple[str, str, str, Path, _Collector]] = [
        ("user-skills", "Personal skills", "user", claude_home / "skills", _skills_in),
        ("user-commands", "Personal commands", "user", claude_home / "commands", _commands_in),
    ]
    if project is not None:
        lookups.append(
            ("project-skills", "Project skills", "project", project / ".claude" / "skills", _skills_in)
        )
        lookups.append(
            (
                "project-commands",
                "Project commands",
                "project",
                project / ".claude" / "commands",
                _commands_in,
            )
        )

    for key, label, scope, directory, collector in lookups:
        found = collector(directory, scope)
        records.extend(found)
        sources.append(
            SkillSource(
                key=key,
                label=label,
                scope=scope,
                path=directory,
                exists=directory.is_dir(),
                count=len(found),
            )
        )

    for entry in _installed_plugins(claude_home, project):
        found = _plugin_records(entry)
        records.extend(found)
        root = Path(entry["root"])
        sources.append(
            SkillSource(
                key=f"plugin-{entry['plugin']}",
                label=f"{entry['plugin']} plugin",
                scope="plugin",
                path=root,
                exists=root.is_dir(),
                count=len(found),
                plugin_version=entry["version"],
                plugin_enabled=bool(entry["enabled"]),
            )
        )

    return tuple(records), tuple(sources)
