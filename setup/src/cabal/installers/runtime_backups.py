# -*- coding: utf-8 -*-
"""Runtime backup records captured before install or upgrade actions."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cabal.installers.versions import installed_version_for
from cabal.tool_catalog import redact_secret_text


RUNTIME_BACKUP_KEYS = {"bun", "npm", "pnpm", "python", "node", "dotnet"}


@dataclass(frozen=True)
class RuntimeBackupRecord:
    tool_key: str
    created_at: str
    before_version: str | None
    before_path: str | None
    install_channel: str
    config_paths: tuple[str, ...] = field(default_factory=tuple)
    restore_hint: str = ""
    artifact_path: str | None = None


def default_backup_root() -> Path:
    return Path.home() / ".cabal" / "runtime-backups"


def detect_install_channel(tool_key: str, executable_path: str | None) -> str:
    if not executable_path:
        return "unknown"
    lowered = executable_path.lower()
    if "scoop" in lowered:
        return "scoop"
    if "chocolatey" in lowered or "choco" in lowered:
        return "chocolatey"
    if "winget" in lowered or "windowsapps" in lowered:
        return "winget"
    if "homebrew" in lowered or "/brew/" in lowered:
        return "homebrew"
    if "/usr/bin" in lowered or "/usr/local/bin" in lowered:
        return "system-package"
    if tool_key in {"npm", "pnpm", "bun"}:
        return "node-package-manager"
    return "manual-or-path"


def safe_config_paths(tool_key: str) -> tuple[str, ...]:
    home = Path.home()
    candidates: dict[str, tuple[Path, ...]] = {
        "npm": (home / ".npmrc", home / ".npm"),
        "pnpm": (home / ".npmrc", home / ".pnpm-store"),
        "bun": (home / ".bunfig.toml", home / ".bun"),
        "python": (home / "pip", home / ".config" / "pip"),
        "node": (home / ".npmrc", home / ".node_repl_history"),
        "dotnet": (home / ".nuget", home / ".dotnet"),
    }
    return tuple(str(path) for path in candidates.get(tool_key, ()) if path.exists())


def restore_hint_for(tool_key: str, install_channel: str) -> str:
    base = (
        f"Restore {tool_key} using its previous package manager or manual installer. "
        "This record captures recovery evidence, not a full binary rollback."
    )
    if install_channel in {"winget", "scoop", "chocolatey", "homebrew", "system-package"}:
        return f"{base} Reinstall the prior version through {install_channel} if that channel supports pinning."
    if install_channel == "node-package-manager":
        return f"{base} Reinstall the prior global package version with npm/pnpm/bun if needed."
    return base


def create_runtime_backup_record(
    tool_key: str,
    *,
    root: Path | None = None,
) -> RuntimeBackupRecord:
    if tool_key not in RUNTIME_BACKUP_KEYS:
        raise ValueError(f"unsupported runtime backup key: {tool_key}")

    executable_name = "python" if tool_key == "python" else tool_key
    executable_path = shutil.which(executable_name)
    install_channel = detect_install_channel(tool_key, executable_path)
    created_at = datetime.now(timezone.utc).isoformat()
    record = RuntimeBackupRecord(
        tool_key=tool_key,
        created_at=created_at,
        before_version=installed_version_for(tool_key),
        before_path=executable_path,
        install_channel=install_channel,
        config_paths=safe_config_paths(tool_key),
        restore_hint=restore_hint_for(tool_key, install_channel),
    )

    backup_root = root or default_backup_root()
    backup_root.mkdir(parents=True, exist_ok=True)
    safe_ts = created_at.replace(":", "").replace("+", "Z")
    path = backup_root / f"{tool_key}-{safe_ts}.json"
    payload = asdict(record)
    text = redact_secret_text(json.dumps(payload, indent=2, sort_keys=True))
    path.write_text(text + "\n", encoding="utf-8")

    return RuntimeBackupRecord(**{**payload, "artifact_path": str(path)})


def backup_before_install(tool_key: str) -> tuple[bool, str]:
    try:
        record = create_runtime_backup_record(tool_key)
    except Exception as exc:
        return False, redact_secret_text(f"Runtime backup failed for {tool_key}: {exc}")
    return True, redact_secret_text(
        f"Runtime backup recorded for {tool_key}: {record.artifact_path}\n{record.restore_hint}"
    )
