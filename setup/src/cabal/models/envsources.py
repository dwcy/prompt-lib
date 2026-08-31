# -*- coding: utf-8 -*-
"""Pure dataclasses for the environment-variable source browser — no I/O, no network.

`VariableEntry` deliberately has no `value` field: the listing route serialises these
objects directly, so the absence of the field is what makes a value leak impossible
rather than a convention someone has to remember (FR-008, data-model rule 3).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

__all__ = [
    "AvailabilityState",
    "AzureProjectLink",
    "ConfigLayer",
    "LinkConfidence",
    "Retrievability",
    "RevealResult",
    "SourceKind",
    "VariableContainer",
    "VariableEntry",
    "VariableSource",
    "source_payload",
]


class AvailabilityState(str, Enum):
    """The four outcomes a source may report (FR-037).

    Deliberately its own enum rather than an extension of `models/dashboard.AvailabilityState`:
    this module emits exactly these four, and the dashboard's six failure values
    (`no_cli`, `not_authed`, `token_missing`, `token_rejected`, `timeout`, `error`) are all
    collapsed into `degraded` with a hint here, because the reader needs one prompt to act on
    rather than a taxonomy to interpret. Widening the shared enum would also oblige every
    existing dashboard consumer to handle two values it can never receive.
    """

    OK = "ok"
    EMPTY = "empty"
    DEGRADED = "degraded"
    NOT_LINKED = "not_linked"


class SourceKind(str, Enum):
    REPO_FILE = "repo_file"
    DOTNET_SECRETS = "dotnet_secrets"
    DOTNET_LAUNCH_PROFILE = "dotnet_launch_profile"
    AZURE_KEYVAULT = "azure_keyvault"
    AZURE_APP_SETTINGS = "azure_app_settings"
    VERCEL = "vercel"
    GITHUB = "github"


class Retrievability(str, Enum):
    READABLE = "readable"
    PERMISSION_GATED = "permission_gated"
    NEVER = "never"


class LinkConfidence(str, Enum):
    EXPLICIT = "explicit"
    AZD = "azd"
    IAC = "iac"
    MACHINE_DEFAULT = "machine_default"


# Highest confidence first; index position is the ladder rank used by FR-030.
LINK_CONFIDENCE_ORDER: tuple[LinkConfidence, ...] = (
    LinkConfidence.EXPLICIT,
    LinkConfidence.AZD,
    LinkConfidence.IAC,
    LinkConfidence.MACHINE_DEFAULT,
)


@dataclass(frozen=True)
class ConfigLayer:
    stack: str
    name: str
    rank: int
    wins: bool = False


@dataclass(frozen=True)
class VariableEntry:
    name: str
    source_id: str
    container_id: str
    description: str = ""
    target: str | None = None
    entry_type: str | None = None
    updated_at: str | None = None
    retrievability: Retrievability = Retrievability.READABLE
    retrievability_reason: str | None = None
    is_reference: bool = False


@dataclass
class VariableContainer:
    id: str
    source_id: str
    label: str
    qualifier: str | None = None
    layer: ConfigLayer | None = None
    entries: list[VariableEntry] = field(default_factory=list)


@dataclass
class VariableSource:
    id: str
    kind: SourceKind
    label: str
    state: AvailabilityState
    hint: str | None = None
    outside_repository: bool = False
    link_confidence: LinkConfidence | None = None
    link_reason: str | None = None
    containers: list[VariableContainer] = field(default_factory=list)


@dataclass(frozen=True)
class AzureProjectLink:
    subscription_id: str | None
    resource_group: str | None
    confidence: LinkConfidence
    reason: str
    is_explicit: bool = False


@dataclass(frozen=True)
class RevealResult:
    status: str
    value: str | None = None
    reason: str | None = None
    is_reference: bool = False


def source_payload(source: VariableSource) -> dict:
    """Wire form of one source: enums flattened to their string values."""
    return asdict(source, dict_factory=_enum_safe_dict)


def _enum_safe_dict(pairs: list[tuple[str, object]]) -> dict:
    return {key: value.value if isinstance(value, Enum) else value for key, value in pairs}
