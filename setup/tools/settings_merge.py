#!/usr/bin/env python3
"""Add-only merge for ~/.claude/settings.json + install manifest + uninstall.

Re-homed from the removed setup/apply.py. Pure, importable functions plus a
small CLI:

    python setup/tools/settings_merge.py merge [--dry-run]   # merge source -> target
    python setup/tools/settings_merge.py uninstall           # remove deployed files

Add-only merge preserves user-added top-level keys, one-level-deep map entries
(`mcpServers.<name>`, `hooks.<event>`), and list items; the source wins only on
keys it actually defines. Refuses to merge into an unparseable target. The
install manifest records every deployed file (path + sha256) so `uninstall` can
remove exactly what was deployed and skip anything the user has since edited.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2]
GLOBAL_SETTINGS = REPO_DIR / "global" / "settings.json"
TARGET = Path.home() / ".claude"
MANIFEST_PATH = TARGET / ".promptlib-applied.json"


# --- add-only merge ----------------------------------------------------------


def _load_json_or_none(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def merge_settings(src_path: Path, dst_path: Path) -> dict:
    src_data = json.loads(src_path.read_text(encoding="utf-8"))
    if not dst_path.exists():
        return src_data
    try:
        dst_data = json.loads(dst_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Cannot merge into unparseable {dst_path}: {e}") from e
    return _merge_top_level(src_data, dst_data)


def _merge_top_level(src: dict, dst: dict) -> dict:
    merged: dict = dict(dst)
    for key, src_val in src.items():
        if key not in merged:
            merged[key] = src_val
            continue
        dst_val = merged[key]
        if isinstance(src_val, dict) and isinstance(dst_val, dict):
            merged[key] = _merge_one_level_map(src_val, dst_val)
        elif isinstance(src_val, list) and isinstance(dst_val, list):
            merged[key] = _merge_list(src_val, dst_val)
        else:
            merged[key] = src_val
    return merged


def _merge_one_level_map(src: dict, dst: dict) -> dict:
    merged: dict = dict(dst)
    for key, src_val in src.items():
        if key not in merged:
            merged[key] = src_val
            continue
        dst_val = merged[key]
        if isinstance(src_val, list) and isinstance(dst_val, list):
            merged[key] = _merge_list(src_val, dst_val)
        else:
            merged[key] = src_val
    return merged


def _merge_list(src: list, dst: list) -> list:
    out = list(dst)
    for item in src:
        if item not in out:
            out.append(item)
    return out


# --- install manifest --------------------------------------------------------


@dataclass
class ManifestEntry:
    path: str
    sha256: str
    deployed_at: str


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest() -> list[ManifestEntry]:
    if not MANIFEST_PATH.exists():
        return []
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    out: list[ManifestEntry] = []
    for entry in data.get("files") or []:
        try:
            out.append(
                ManifestEntry(entry["path"], entry["sha256"], entry["deployed_at"])
            )
        except (KeyError, TypeError):
            continue
    return out


def write_manifest(applied: list[Path]) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    existing = {e.path: e for e in read_manifest()}
    for abs_path in applied:
        if not abs_path.exists():
            continue
        rel = abs_path.relative_to(TARGET).as_posix()
        existing[rel] = ManifestEntry(rel, _sha256_file(abs_path), now_iso)
    payload = {
        "version": 1,
        "applied_at": now_iso,
        "files": [
            {"path": e.path, "sha256": e.sha256, "deployed_at": e.deployed_at}
            for e in sorted(existing.values(), key=lambda x: x.path)
        ],
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# --- uninstall ---------------------------------------------------------------


def _uninstall() -> int:
    if not MANIFEST_PATH.exists():
        print("No manifest found - nothing to uninstall.")
        return 0
    entries = read_manifest()
    removed: list[str] = []
    skipped: list[str] = []
    for entry in entries:
        abs_path = TARGET / entry.path
        if abs_path.exists() and _sha256_file(abs_path) == entry.sha256:
            try:
                abs_path.unlink()
                removed.append(entry.path)
            except OSError:
                skipped.append(entry.path)
        else:
            skipped.append(entry.path)
    for rel in removed:
        print(f"  removed  {rel}")
    if skipped:
        print(f"  skipped {len(skipped)} file(s) (modified since deploy or missing):")
        for rel in skipped:
            print(f"    - {rel}")
    if skipped:
        _prune_manifest(skipped)  # keep only the entries we couldn't remove
    else:
        MANIFEST_PATH.unlink(missing_ok=True)
    print(f"Uninstall complete: {len(removed)} removed, {len(skipped)} skipped.")
    return 0


def _prune_manifest(keep_paths: list[str]) -> None:
    """Keep only the named entries in the manifest (those we couldn't remove)."""
    keep = set(keep_paths)
    survivors = [e for e in read_manifest() if e.path in keep]
    payload = {
        "version": 1,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "files": [
            {"path": e.path, "sha256": e.sha256, "deployed_at": e.deployed_at}
            for e in sorted(survivors, key=lambda x: x.path)
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# --- CLI ---------------------------------------------------------------------


def _apply_merge(dry_run: bool) -> int:
    dst = TARGET / "settings.json"
    try:
        merged = merge_settings(GLOBAL_SETTINGS, dst)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    existing = _load_json_or_none(dst)
    if existing == merged:
        print("settings.json: up to date (no changes).")
        return 0
    if dry_run:
        print("settings.json: WOULD CHANGE (add-only merge). Merged result:")
        print(json.dumps(merged, indent=2))
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    write_manifest([dst])
    print(f"settings.json: merged (user keys preserved) -> {dst}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add-only settings merge / uninstall.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_merge = sub.add_parser(
        "merge", help="merge global/settings.json into ~/.claude/settings.json"
    )
    p_merge.add_argument(
        "--dry-run", action="store_true", help="show the merge without writing"
    )
    sub.add_parser("uninstall", help="remove files recorded in the install manifest")
    args = parser.parse_args(argv)
    if args.cmd == "merge":
        return _apply_merge(args.dry_run)
    if args.cmd == "uninstall":
        return _uninstall()
    return 2


if __name__ == "__main__":
    sys.exit(main())
