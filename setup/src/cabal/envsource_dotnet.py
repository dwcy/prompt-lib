# -*- coding: utf-8 -*-
"""".NET configuration shape for the environment browser: key flattening, layer precedence,
launch profiles, and the developer secret store that lives outside the repository.

Reports an ordering, never a merged effective value (FR-043): the value an app actually reads
also depends on command-line arguments and process environment variables, which this module
cannot observe, so a merged result would be confidently wrong exactly when someone is debugging.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from cabal.models.envsources import (
    AvailabilityState,
    ConfigLayer,
    Retrievability,
    SourceKind,
    VariableContainer,
    VariableEntry,
    VariableSource,
)

STACK = "dotnet"
KEY_SEPARATOR = ":"

# Research R3, highest priority first. Command line (1) and environment variables (2) are
# real layers this module cannot observe, so the ranks it can assign start at 3.
RANK_USER_SECRETS = 3
RANK_ENVIRONMENT_SETTINGS = 4
RANK_BASE_SETTINGS = 5

_PROJECT_SUFFIXES = (".csproj", ".fsproj", ".vbproj")
_USER_SECRETS_ID = re.compile(r"<UserSecretsId>\s*([^<\s]+)\s*</UserSecretsId>", re.IGNORECASE)
_APPSETTINGS_ENV = re.compile(r"^appsettings\.(?P<env>.+)\.json$", re.IGNORECASE)

_LAUNCH_SETTINGS = "launchsettings.json"
_SECRETS_FILE = "secrets.json"

_HINT_SECRETS_UNREADABLE = "the secret store for {id} could not be read: {detail}"
_REASON_OUTSIDE = "stored outside the repository by the .NET Secret Manager"


@dataclass(frozen=True)
class UserSecretsDeclaration:
    """A `<UserSecretsId>` the selected project declares, and where the platform keeps it."""

    secrets_id: str
    project_file: str
    store: Path


def flatten_json_keys(document: dict, prefix: str = "") -> list[str]:
    """Fully-qualified leaf paths for a settings document (FR-040).

    A section holding only sections is never listed in its own right (FR-041); an empty
    object or array is a leaf, because it is a value the framework binds.
    """
    keys: list[str] = []
    for raw_key, value in document.items():
        key = str(raw_key)
        path = f"{prefix}{KEY_SEPARATOR}{key}" if prefix else key
        keys.extend(_flatten_value(value, path))
    return keys


def _flatten_value(value: object, path: str) -> list[str]:
    if isinstance(value, dict) and value:
        return flatten_json_keys(value, path)
    if isinstance(value, list) and value:
        keys: list[str] = []
        for index, item in enumerate(value):
            keys.extend(_flatten_value(item, f"{path}{KEY_SEPARATOR}{index}"))
        return keys
    return [path]


def lookup_flattened(document: dict, name: str) -> str | None:
    """Resolve a colon-delimited leaf path back to its literal value, or None if absent."""
    node: object = document
    for segment in name.split(KEY_SEPARATOR):
        if isinstance(node, dict) and segment in node:
            node = node[segment]
            continue
        if isinstance(node, list) and segment.isdigit() and int(segment) < len(node):
            node = node[int(segment)]
            continue
        return None
    if node is None:
        return ""
    if isinstance(node, bool):
        return "true" if node else "false"
    if isinstance(node, (dict, list)):
        return json.dumps(node)
    return str(node)


def layer_for(file_name: str) -> ConfigLayer | None:
    """The .NET precedence layer a settings file occupies, or None if it is not one."""
    lowered = file_name.lower()
    if lowered == "appsettings.json":
        return ConfigLayer(stack=STACK, name=file_name, rank=RANK_BASE_SETTINGS)
    if _APPSETTINGS_ENV.match(lowered):
        return ConfigLayer(stack=STACK, name=file_name, rank=RANK_ENVIRONMENT_SETTINGS)
    return None


def user_secrets_store(secrets_id: str) -> Path:
    """Platform path of the Secret Manager store for `secrets_id` (research R4)."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return root / "Microsoft" / "UserSecrets" / secrets_id / _SECRETS_FILE
    return Path.home() / ".microsoft" / "usersecrets" / secrets_id / _SECRETS_FILE


def find_user_secrets(project: Path) -> list[UserSecretsDeclaration]:
    """Every secret store the SELECTED project declares — never any other project's (FR-047)."""
    from cabal.envsource_discovery import MAX_DEPTH, SKIPPED_DIRS

    declarations: dict[str, UserSecretsDeclaration] = {}
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
                if depth < MAX_DEPTH and child.name not in SKIPPED_DIRS:
                    frontier.append((child, depth + 1))
                continue
            if child.suffix.lower() not in _PROJECT_SUFFIXES:
                continue
            secrets_id = _read_user_secrets_id(child)
            if secrets_id is None or secrets_id in declarations:
                continue
            declarations[secrets_id] = UserSecretsDeclaration(
                secrets_id=secrets_id,
                project_file=_relative(child, project),
                store=user_secrets_store(secrets_id),
            )
    return list(declarations.values())


def _read_user_secrets_id(project_file: Path) -> str | None:
    try:
        text = project_file.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    match = _USER_SECRETS_ID.search(text)
    if match is None:
        return None
    secrets_id = match.group(1).strip()
    # The id becomes a path segment; anything that could climb out of the store root is
    # not an id this module will follow (FR-047).
    if not secrets_id or "/" in secrets_id or "\\" in secrets_id or ".." in secrets_id:
        return None
    return secrets_id


def build_dotnet_sources(project: Path, discovered) -> list[VariableSource]:
    """Sources for the .NET-shaped files in `discovered`, plus any declared secret store."""
    from cabal.envsource_discovery import read_keys, source_id_for

    settings = [item for item in discovered if layer_for(item.label) is not None]
    launch = [item for item in discovered if item.label.lower() == _LAUNCH_SETTINGS]

    sources = _settings_sources(settings, read_keys, source_id_for)
    sources.extend(_launch_sources(launch, source_id_for))
    sources.extend(_secret_store_sources(project))
    return sources


def _settings_sources(settings, read_keys, source_id_for) -> list[VariableSource]:
    parsed = []
    for item in settings:
        names, state, hint = read_keys(item.path)
        parsed.append((item, names, state, hint))
    winners = _winning_layers(parsed)

    sources: list[VariableSource] = []
    for item, names, state, hint in parsed:
        source_id = source_id_for(item)
        layer = layer_for(item.label)
        group = str(item.path.parent)
        container = VariableContainer(
            id=source_id,
            source_id=source_id,
            label=item.label,
            qualifier=item.qualifier,
            layer=layer,
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
        if layer is not None:
            container.layer = ConfigLayer(
                stack=layer.stack,
                name=layer.name,
                rank=layer.rank,
                wins=all(winners.get((group, name)) == source_id for name in names) and bool(names),
            )
        sources.append(
            VariableSource(
                id=source_id,
                kind=SourceKind.REPO_FILE,
                label=item.label,
                state=state,
                hint=hint,
                containers=[] if state is AvailabilityState.DEGRADED else [container],
            )
        )
    return sources


def _winning_layers(parsed) -> dict[tuple[str, str], str | None]:
    """Which source id defines each key at the lowest discovered rank, per project directory.

    None where two discovered layers tie on rank — `appsettings.Development.json` and
    `appsettings.Production.json` never load together, so neither can be called the winner.
    """
    from cabal.envsource_discovery import source_id_for

    best: dict[tuple[str, str], tuple[int, str | None]] = {}
    for item, names, _state, _hint in parsed:
        layer = layer_for(item.label)
        if layer is None:
            continue
        source_id = source_id_for(item)
        group = str(item.path.parent)
        for name in names:
            key = (group, name)
            current = best.get(key)
            if current is None or layer.rank < current[0]:
                best[key] = (layer.rank, source_id)
            elif layer.rank == current[0] and current[1] != source_id:
                best[key] = (layer.rank, None)
    return {key: value[1] for key, value in best.items()}


def _launch_sources(launch, source_id_for) -> list[VariableSource]:
    sources: list[VariableSource] = []
    for item in launch:
        source_id = source_id_for(item)
        containers, state, hint = _launch_containers(item, source_id)
        sources.append(
            VariableSource(
                id=source_id,
                kind=SourceKind.DOTNET_LAUNCH_PROFILE,
                label=item.label,
                state=state,
                hint=hint,
                containers=containers,
            )
        )
    return sources


def _launch_containers(item, source_id: str):
    """One container per launch profile that injects environment variables (FR-042)."""
    from cabal.envsource_discovery import read_keys

    try:
        document = json.loads(item.path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, ValueError):
        _names, state, hint = read_keys(item.path)
        return [], state, hint
    profiles = document.get("profiles") if isinstance(document, dict) else None
    if not isinstance(profiles, dict):
        return [], AvailabilityState.EMPTY, None

    containers: list[VariableContainer] = []
    for profile_name, profile in profiles.items():
        variables = profile.get("environmentVariables") if isinstance(profile, dict) else None
        if not isinstance(variables, dict) or not variables:
            continue
        container_id = f"{source_id}#{profile_name}"
        containers.append(
            VariableContainer(
                id=container_id,
                source_id=source_id,
                label=str(profile_name),
                qualifier=item.qualifier or item.label,
                entries=[
                    VariableEntry(
                        name=str(name),
                        source_id=source_id,
                        container_id=container_id,
                        target=str(profile_name),
                        retrievability=Retrievability.READABLE,
                    )
                    for name in variables
                ],
            )
        )
    return containers, AvailabilityState.OK if containers else AvailabilityState.EMPTY, None


def _secret_store_sources(project: Path) -> list[VariableSource]:
    sources: list[VariableSource] = []
    for declaration in find_user_secrets(project):
        source_id = f"{SourceKind.DOTNET_SECRETS.value}:{declaration.secrets_id}"
        names, state, hint = _read_secret_store(declaration)
        container = VariableContainer(
            id=source_id,
            source_id=source_id,
            label=f"User secrets ({declaration.secrets_id})",
            qualifier=declaration.project_file,
            layer=ConfigLayer(
                stack=STACK, name="User secrets", rank=RANK_USER_SECRETS, wins=False
            ),
            entries=[
                VariableEntry(
                    name=name,
                    source_id=source_id,
                    container_id=source_id,
                    description=_REASON_OUTSIDE,
                    retrievability=Retrievability.READABLE,
                )
                for name in names
            ],
        )
        sources.append(
            VariableSource(
                id=source_id,
                kind=SourceKind.DOTNET_SECRETS,
                label="User secrets",
                state=state,
                hint=hint,
                outside_repository=True,
                containers=[] if state is AvailabilityState.DEGRADED else [container],
            )
        )
    return sources


def _read_secret_store(declaration: UserSecretsDeclaration):
    """A declared store that was never populated is empty, not missing (FR-046)."""
    if not declaration.store.is_file():
        return [], AvailabilityState.EMPTY, None
    try:
        document = json.loads(declaration.store.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        detail = str(exc).strip() or type(exc).__name__
        hint = _HINT_SECRETS_UNREADABLE.format(id=declaration.secrets_id, detail=detail)
        return [], AvailabilityState.DEGRADED, hint
    if not isinstance(document, dict):
        return [], AvailabilityState.EMPTY, None
    keys = flatten_json_keys(document)
    return keys, AvailabilityState.OK if keys else AvailabilityState.EMPTY, None


def read_secret_value(secrets_id: str, name: str) -> str | None:
    store = user_secrets_store(secrets_id)
    try:
        document = json.loads(store.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return lookup_flattened(document, name) if isinstance(document, dict) else None


def _relative(path: Path, project: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return path.name
