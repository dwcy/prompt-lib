# -*- coding: utf-8 -*-
"""Tools module aggregation: catalog payload composition and definitive status probing.

Bridges the two Cabal tool registries the same way `cabal.views.tools.ToolsScreen`
already does: `cabal.tool_catalog` owns row metadata (label/category/source/versions),
`cabal.tools` owns the callable probes/installers keyed by the same catalog key.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from cabal.env_detect import _dotnet_sdks
from cabal.installers.dotnet_releases import get_cached_release_set
from cabal.installers.versions import version_options_for
from cabal.tool_catalog import TOOL_CATEGORIES, TOOL_DEFINITIONS, ToolDefinition, get_tool_definition
from cabal.tools import VERSION_FLOORS, _below_floor, _outdated_packages, _probe_key, _tool_unavailable_reason
from cabal.webapi.envelope import utc_now_iso

_MAX_PROBE_WORKERS = 8


def catalog_payload() -> dict[str, Any]:
    """`/api/tools` data: catalog metadata (no per-item status) plus category/channel counts."""
    items = [_catalog_item(definition) for definition in TOOL_DEFINITIONS]
    category_counts = {category.name: len(category.keys) for category in TOOL_CATEGORIES}
    channel_counts: dict[str, int] = {}
    for definition in TOOL_DEFINITIONS:
        channel = definition.install_channel.value
        channel_counts[channel] = channel_counts.get(channel, 0) + 1
    return {"items": items, "category_counts": category_counts, "channel_counts": channel_counts}


def _catalog_item(definition: ToolDefinition) -> dict[str, Any]:
    versions_available: list[str] = []
    if definition.version_provider:
        result = version_options_for(definition.version_provider)
        versions_available = [option.label for option in result.options]

    safety_notes: list[str] = []
    reason = _tool_unavailable_reason(definition.key)
    if reason:
        safety_notes.append(reason)
    if definition.backup_policy:
        safety_notes.append(f"Runtime backup captured before install/update ({definition.backup_policy}).")

    return {
        "key": definition.key,
        "label": definition.label,
        "category": definition.category,
        "description": definition.description,
        "source_url": definition.source_url,
        "source_state": definition.source_status.value,
        "install_channel": definition.install_channel.value,
        "platforms": list(definition.platforms),
        "badges": list(definition.badges),
        "safety_notes": safety_notes,
        "backup_policy": definition.backup_policy,
        "versions_available": versions_available,
    }


def probe_all_status() -> list[dict[str, Any]]:
    """`/api/tools/status` data: every catalog key resolved to a definitive ToolStatus.

    Parallelized (thread pool) since the underlying probes are subprocess/network I/O;
    the outdated-package sweep (winget/npm-registry) runs exactly once for the batch.
    """
    outdated = _safe_outdated_packages()
    with ThreadPoolExecutor(max_workers=_MAX_PROBE_WORKERS) as pool:
        futures = {
            definition.key: pool.submit(_status_for, definition, outdated) for definition in TOOL_DEFINITIONS
        }
        return [{"key": key, **future.result()} for key, future in futures.items()]


def probe_one_status(key: str) -> dict[str, Any] | None:
    """`/api/tools/{key}/status` data, or None for an unknown catalog key."""
    definition = get_tool_definition(key)
    if definition is None:
        return None
    reason = _tool_unavailable_reason(key)
    if reason is not None:
        return _reason_status(definition)
    outdated = _safe_outdated_packages()
    return _probe_installed(definition, outdated)


def build_tool_detail(key: str) -> dict[str, Any] | None:
    """`/api/tools/{key}` data: full catalog item plus its embedded status, or None."""
    definition = get_tool_definition(key)
    if definition is None:
        return None
    item = _catalog_item(definition)
    item["status"] = probe_one_status(key)
    return item


def _status_for(definition: ToolDefinition, outdated: set[str]) -> dict[str, Any]:
    reason = _tool_unavailable_reason(definition.key)
    if reason is not None:
        return _reason_status(definition)
    return _probe_installed(definition, outdated)


def _reason_status(definition: ToolDefinition) -> dict[str, Any]:
    state = "unsupported" if not definition.supports_current_platform else "manual_required"
    return _status_dict(state, None, None)


def _probe_installed(definition: ToolDefinition, outdated: set[str]) -> dict[str, Any]:
    key = definition.key
    try:
        probe_value = _probe_key(key)
        sdks = _dotnet_sdks() if key == "dotnet" else None
    except Exception:
        return _status_dict("error", None, None)

    installed, current_version = _classify_probe(key, probe_value, sdks)
    if not installed:
        return _status_dict("missing", None, None)

    floor_value = sdks if key == "dotnet" else probe_value
    is_outdated = key in outdated or (key in VERSION_FLOORS and _below_floor(key, floor_value))
    state = "update_available" if is_outdated else "installed"
    return _status_dict(state, current_version, _latest_version_for(key))


def _classify_probe(key: str, probe_value: object, sdks: list[str] | None) -> tuple[bool, str | None]:
    if key == "dotnet" and sdks:
        return True, ", ".join(sdks)
    if isinstance(probe_value, str) and probe_value:
        return True, probe_value
    return bool(probe_value), None


def _latest_version_for(key: str) -> str | None:
    """Best-effort known-latest version string; None when no live provider covers `key`."""
    if key != "dotnet":
        return None
    release_set = get_cached_release_set()
    if release_set is None or release_set.latest_lts is None:
        return None
    return release_set.latest_lts.latest_sdk


def _status_dict(state: str, current_version: str | None, latest_version: str | None) -> dict[str, Any]:
    return {
        "state": state,
        "current_version": current_version,
        "latest_version": latest_version,
        "checked_at": utc_now_iso(),
    }


def _safe_outdated_packages() -> set[str]:
    try:
        return _outdated_packages()
    except Exception:
        return set()
