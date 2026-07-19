# -*- coding: utf-8 -*-
"""Read model for the Settings module: each cataloged boolean setting with its source
provenance (global baseline / local override / unset) and effective value. Wraps
cabal.claude_settings; the toggle/reset mutations live in the action registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cabal.claude_settings import (
    CATALOG,
    effective_value,
    global_settings_path,
    local_settings_path,
    read_global,
    read_local,
)


def settings_entries(project: Path | None) -> dict[str, Any]:
    """`/api/settings` data: SettingEntry[] with source markers and effective values."""
    global_values = read_global()
    local_values = read_local(project) if project is not None else {}
    target_file = str(local_settings_path(project)) if project is not None else str(global_settings_path())

    entries = []
    for setting in CATALOG:
        if setting.key in local_values:
            source = "local_override"
        elif setting.key in global_values:
            source = "global"
        else:
            source = "unset"
        entries.append(
            {
                "key": setting.key,
                "label": setting.label,
                "description": setting.description,
                "source": source,
                "value_state": effective_value(setting, global_values, local_values),
                "target_file": target_file,
            }
        )
    return {"entries": entries, "project_selected": project is not None}
