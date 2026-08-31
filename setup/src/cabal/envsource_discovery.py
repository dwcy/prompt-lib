# -*- coding: utf-8 -*-
"""Repo config-file discovery and key listing for the environment browser — file reads only.

Deliberately ignores .gitignore: `.env.local` and friends are excluded from version control
precisely because they hold the real local configuration, which is what makes them worth
listing (FR-026). Dependency, build-output, and VCS-internal directories are skipped instead
(FR-027), which is what keeps a monorepo scan bounded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cabal.models.envsources import (
    AvailabilityState,
    Retrievability,
    SourceKind,
    VariableContainer,
    VariableEntry,
    VariableSource,
)

MAX_DEPTH = 6
MAX_FILES = 60
MAX_FILE_BYTES = 512 * 1024

SKIPPED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "bower_components",
        "vendor",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "dist",
        "build",
        "out",
        "bin",
        "obj",
        "target",
        "coverage",
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".turbo",
        ".parcel-cache",
        ".gradle",
        ".idea",
        ".vs",
        ".terraform",
    }
)

_DOTENV_PREFIX = ".env"
_APPSETTINGS_PREFIX = "appsettings"
_LAUNCH_SETTINGS = "launchsettings.json"
_ENV_JSON_SUFFIX = ".env.json"

_HINT_UNREADABLE = "{name} could not be read: {detail}"
_HINT_MALFORMED = "{name} is not valid {fmt}: {detail}"
_HINT_TOO_LARGE = "{name} is larger than {limit} KiB and was not parsed"
_NOTICE_CAP = "Stopped after {limit} config files; the project holds more."


@dataclass(frozen=True)
class DiscoveredFile:
    """One config file found in the project, with the path pieces the UI needs to label it."""

    path: Path
    relative: str
    label: str
    qualifier: str | None
    kind: SourceKind


def discover_config_files(
    project: Path, *, max_depth: int = MAX_DEPTH, max_files: int = MAX_FILES
) -> tuple[list[DiscoveredFile], list[str]]:
    """Return the config files under `project` plus any notices about what was left out."""
    found: list[DiscoveredFile] = []
    notices: list[str] = []
    truncated = False

    for path in _walk(project, max_depth):
        if len(found) >= max_files:
            truncated = True
            break
        if not _is_config_file(path):
            continue
        found.append(_describe(path, project))

    if truncated:
        notices.append(_NOTICE_CAP.format(limit=max_files))
    found.sort(key=lambda item: (item.relative.count("/"), item.relative.lower()))
    return _apply_qualifiers(found), notices


def _walk(project: Path, max_depth: int):
    """Breadth-first walk skipping dependency/build/VCS trees, bounded by `max_depth`."""
    frontier = [(project, 0)]
    while frontier:
        directory, depth = frontier.pop(0)
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue
        for child in children:
            try:
                is_dir = child.is_dir()
            except OSError:
                continue
            if is_dir:
                if depth < max_depth and child.name not in SKIPPED_DIRS:
                    frontier.append((child, depth + 1))
                continue
            yield child


def _is_config_file(path: Path) -> bool:
    name = path.name
    lowered = name.lower()
    if lowered == _LAUNCH_SETTINGS and path.parent.name.lower() == "properties":
        return True
    if lowered.endswith(_ENV_JSON_SUFFIX):
        return True
    if lowered.startswith(_APPSETTINGS_PREFIX) and lowered.endswith(".json"):
        return True
    if name == _DOTENV_PREFIX or name.startswith(_DOTENV_PREFIX + "."):
        return True
    # `.env` may also trail the name, as in `production.env`.
    return lowered.endswith(_DOTENV_PREFIX)


def _describe(path: Path, project: Path) -> DiscoveredFile:
    try:
        relative = path.relative_to(project).as_posix()
    except ValueError:
        relative = path.name
    try:
        qualifier = path.parent.relative_to(project).as_posix() or None
    except ValueError:
        qualifier = None
    kind = SourceKind.REPO_FILE
    if path.name.lower() == _LAUNCH_SETTINGS:
        kind = SourceKind.DOTNET_LAUNCH_PROFILE
    return DiscoveredFile(
        path=path, relative=relative, label=path.name, qualifier=qualifier, kind=kind
    )


def _apply_qualifiers(found: list[DiscoveredFile]) -> list[DiscoveredFile]:
    """Qualify every file whose name is not unique in the project (data-model rule 4)."""
    counts: dict[str, int] = {}
    for item in found:
        counts[item.label] = counts.get(item.label, 0) + 1
    resolved: list[DiscoveredFile] = []
    for item in found:
        qualifier = item.qualifier if counts[item.label] > 1 else None
        resolved.append(
            DiscoveredFile(
                path=item.path,
                relative=item.relative,
                label=item.label,
                qualifier=qualifier,
                kind=item.kind,
            )
        )
    return resolved


def source_id_for(discovered: DiscoveredFile) -> str:
    return discovered.kind.value + ":" + discovered.relative.replace("/", "~")


def collect_repo_files(project: Path) -> tuple[list[VariableSource], list[str]]:
    """One source per discovered config file; a bad file degrades only its own source (FR-029)."""
    from cabal.envsource_dotnet import build_dotnet_sources

    discovered, notices = discover_config_files(project)
    sources = build_dotnet_sources(project, discovered)
    handled = {source.id for source in sources}
    for item in discovered:
        source_id = source_id_for(item)
        if source_id in handled:
            continue
        sources.append(build_file_source(item))
    return sources, notices


def build_file_source(discovered: DiscoveredFile) -> VariableSource:
    source_id = source_id_for(discovered)
    names, state, hint = read_keys(discovered.path)
    container = VariableContainer(
        id=source_id,
        source_id=source_id,
        label=discovered.label,
        qualifier=discovered.qualifier,
        entries=[
            VariableEntry(
                name=name,
                source_id=source_id,
                container_id=source_id,
                retrievability=Retrievability.READABLE,
            )
            for name in names
        ],
    )
    return VariableSource(
        id=source_id,
        kind=SourceKind.REPO_FILE,
        label=discovered.label,
        state=state,
        hint=hint,
        containers=[] if state is AvailabilityState.DEGRADED else [container],
    )


def read_keys(path: Path) -> tuple[list[str], AvailabilityState, str | None]:
    """Key names declared by one config file, plus the state that file is in."""
    text, state, hint = _read_text(path)
    if text is None:
        return [], state, hint
    if path.suffix.lower() == ".json":
        return _json_keys(path, text)
    return _dotenv_keys(text)


def _read_text(path: Path) -> tuple[str | None, AvailabilityState, str | None]:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            limit = MAX_FILE_BYTES // 1024
            return (
                None,
                AvailabilityState.DEGRADED,
                _HINT_TOO_LARGE.format(name=path.name, limit=limit),
            )
        return path.read_text(encoding="utf-8-sig"), AvailabilityState.OK, None
    except (OSError, UnicodeDecodeError) as exc:
        hint = _HINT_UNREADABLE.format(name=path.name, detail=_detail(exc))
        return None, AvailabilityState.DEGRADED, hint


def _json_keys(path: Path, text: str) -> tuple[list[str], AvailabilityState, str | None]:
    from cabal.envsource_dotnet import flatten_json_keys

    try:
        document = json.loads(text)
    except ValueError as exc:
        hint = _HINT_MALFORMED.format(name=path.name, fmt="JSON", detail=_detail(exc))
        return [], AvailabilityState.DEGRADED, hint
    if not isinstance(document, dict):
        hint = _HINT_MALFORMED.format(
            name=path.name, fmt="JSON", detail="top level is not an object"
        )
        return [], AvailabilityState.DEGRADED, hint
    keys = flatten_json_keys(document)
    return keys, AvailabilityState.OK if keys else AvailabilityState.EMPTY, None


def _dotenv_keys(text: str) -> tuple[list[str], AvailabilityState, str | None]:
    keys: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        name = _dotenv_key(raw)
        if name is None or name in seen:
            # A duplicate key is one row, not two: the file declares one name, and the
            # last assignment wins. Two rows would imply two independent settings.
            continue
        seen.add(name)
        keys.append(name)
    return keys, AvailabilityState.OK if keys else AvailabilityState.EMPTY, None


def _dotenv_key(raw: str) -> str | None:
    line = _strip_export(raw)
    if line is None:
        return None
    name, separator, _rest = line.partition("=")
    name = name.strip()
    return name if separator and name else None


def _strip_export(raw: str) -> str | None:
    line = raw.strip()
    if not line or line.startswith("#"):
        return None
    if line.lower().startswith("export "):
        return line[len("export ") :].lstrip()
    return line


def read_value(path: Path, name: str) -> str | None:
    """The literal value of one key, read at reveal time and never cached (FR-015)."""
    text, state, _hint = _read_text(path)
    if text is None or state is AvailabilityState.DEGRADED:
        return None
    if path.suffix.lower() == ".json":
        from cabal.envsource_dotnet import lookup_flattened

        try:
            document = json.loads(text)
        except ValueError:
            return None
        return lookup_flattened(document, name) if isinstance(document, dict) else None
    return _dotenv_value(text, name)


def _dotenv_value(text: str, name: str) -> str | None:
    found: str | None = None
    for raw in text.splitlines():
        line = _strip_export(raw)
        if line is None:
            continue
        key, separator, rest = line.partition("=")
        if separator and key.strip() == name:
            found = _unquote(rest.strip())
    return found


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _detail(exc: BaseException) -> str:
    return str(exc).strip() or type(exc).__name__
