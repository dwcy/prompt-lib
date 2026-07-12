# -*- coding: utf-8 -*-
"""OpenCode asset preview and apply helpers."""

from __future__ import annotations

import filecmp
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from cabal.codex_setup.paths import CODEX_SOURCE_DIR
from cabal.opencode_setup.paths import OPENCODE_SOURCE_DIR, OPENCODE_TARGET
from cabal.os_filters import _os_should_skip

JSON_MERGE_FILES = {"opencode.json", "tui.json"}


@dataclass(frozen=True)
class OpenCodeAsset:
    key: str
    label: str
    source: Path
    target: Path
    state: str
    group: str


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _merge_dict(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _contains_dict(base: dict, subset: dict) -> bool:
    for key, value in subset.items():
        if key not in base:
            return False
        if isinstance(value, dict):
            if not isinstance(base[key], dict) or not _contains_dict(base[key], value):
                return False
        elif base[key] != value:
            return False
    return True


def _state(source: Path, target: Path) -> str:
    if not target.exists():
        return "NEW"
    if source.name in JSON_MERGE_FILES:
        source_json = _read_json(source)
        target_json = _read_json(target)
        return "UNCHANGED" if _contains_dict(target_json, source_json) else "CHANGED"
    try:
        return "UNCHANGED" if filecmp.cmp(source, target, shallow=False) else "CHANGED"
    except OSError:
        return "CHANGED"


def _iter_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return ()
    return (
        path
        for path in sorted(root.rglob("*"), key=lambda p: p.as_posix())
        if path.is_file() and not _os_should_skip(path.name)
    )


def _asset(key: str, group: str, source: Path, target: Path, label: str) -> OpenCodeAsset:
    return OpenCodeAsset(
        key=key,
        label=label,
        source=source,
        target=target,
        state=_state(source, target),
        group=group,
    )


def _static_assets(target_root: Path, project: bool = False) -> list[OpenCodeAsset]:
    assets: list[OpenCodeAsset] = []
    if not OPENCODE_SOURCE_DIR.exists():
        return assets

    config = OPENCODE_SOURCE_DIR / "opencode.json"
    if config.is_file():
        target = (target_root.parent / "opencode.json") if project else (target_root / "opencode.json")
        assets.append(_asset("config::opencode", "config", config, target, "opencode.json"))

    tui = OPENCODE_SOURCE_DIR / "tui.json"
    if tui.is_file() and not project:
        assets.append(_asset("config::tui", "config", tui, target_root / "tui.json", "tui.json"))

    readme = OPENCODE_SOURCE_DIR / "README.md"
    if readme.is_file() and not project:
        assets.append(
            _asset(
                "docs::readme",
                "docs",
                readme,
                target_root / "prompt-lib" / "README.md",
                "prompt-lib/README.md",
            )
        )

    tools = OPENCODE_SOURCE_DIR / "tools"
    for source in _iter_files(tools):
        rel = source.relative_to(tools)
        target = target_root / "tools" / rel
        assets.append(_asset(f"tools::{rel.as_posix()}", "tools", source, target, f"tools/{rel.as_posix()}"))
    return assets


def _compatible_skill_assets(target_root: Path) -> list[OpenCodeAsset]:
    skills = CODEX_SOURCE_DIR / "skills"
    assets: list[OpenCodeAsset] = []
    if not skills.exists():
        return assets
    for source in _iter_files(skills):
        rel = source.relative_to(skills)
        if rel.name != "SKILL.md":
            continue
        target = target_root / "skills" / rel
        assets.append(_asset(f"skills::{rel.as_posix()}", "skills", source, target, f"skills/{rel.as_posix()}"))
    return assets


def _reference_assets(target_root: Path) -> list[OpenCodeAsset]:
    references = CODEX_SOURCE_DIR / "references"
    assets: list[OpenCodeAsset] = []
    if not references.exists():
        return assets
    for source in _iter_files(references):
        rel = source.relative_to(references)
        target = target_root / "prompt-lib" / "references" / rel
        assets.append(_asset(f"refs::{rel.as_posix()}", "references", source, target, f"prompt-lib/references/{rel.as_posix()}"))
    return assets


def build_global_plan(target_root: Path = OPENCODE_TARGET) -> list[OpenCodeAsset]:
    return [
        *_static_assets(target_root, project=False),
        *_compatible_skill_assets(target_root),
        *_reference_assets(target_root),
    ]


def build_project_plan(project_dir: Path) -> list[OpenCodeAsset]:
    opencode_dir = project_dir / ".opencode"
    return [
        *_static_assets(opencode_dir, project=True),
        *_compatible_skill_assets(opencode_dir),
    ]


def apply_assets(assets: Iterable[OpenCodeAsset]) -> tuple[int, int]:
    copied = skipped = 0
    for asset in assets:
        if asset.state == "UNCHANGED":
            skipped += 1
            continue
        asset.target.parent.mkdir(parents=True, exist_ok=True)
        if asset.source.name in JSON_MERGE_FILES and asset.target.exists():
            merged = _merge_dict(_read_json(asset.target), _read_json(asset.source))
            text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
            json.loads(text)
            asset.target.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(asset.source, asset.target)
        copied += 1
    return copied, skipped


def has_opencode_deploy_drift(target_root: Path = OPENCODE_TARGET) -> bool:
    return any(asset.state in {"NEW", "CHANGED"} for asset in build_global_plan(target_root))
