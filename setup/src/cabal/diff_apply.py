# -*- coding: utf-8 -*-
"""Diff / apply / backup helpers for the global → ~/.claude/ deploy."""

from __future__ import annotations

import filecmp
import shutil
from datetime import datetime
from pathlib import Path

from cabal._paths import TARGET
from cabal.components import Component, FileStatus
from cabal.settings_helpers import _effective_settings_text, _is_settings_json


def diff_component(comp: Component) -> list[FileStatus]:
    out: list[FileStatus] = []
    for src_file, rel in comp.list_files():
        dst_file = comp.dst_path / rel if comp.type == "dir" else comp.dst_path
        if not dst_file.exists():
            out.append(FileStatus(rel, src_file, dst_file, "NEW"))
        elif _is_settings_json(src_file):
            same = dst_file.read_text(encoding="utf-8") == _effective_settings_text(src_file)
            out.append(FileStatus(rel, src_file, dst_file, "UNCHANGED" if same else "CHANGED"))
        elif filecmp.cmp(src_file, dst_file, shallow=False):
            out.append(FileStatus(rel, src_file, dst_file, "UNCHANGED"))
        else:
            out.append(FileStatus(rel, src_file, dst_file, "CHANGED"))
    return out


def find_extras(comp: Component) -> list[Path]:
    if comp.type == "file" or not comp.dst_path.exists():
        return []
    src_rels = {rel for _, rel in comp.list_files()}
    iterator = comp.dst_path.rglob("*") if comp.recursive else comp.dst_path.glob(comp.glob)
    return [f.relative_to(comp.dst_path) for f in iterator if f.is_file() and f.relative_to(comp.dst_path) not in src_rels]


def apply_statuses(statuses: list[FileStatus]) -> tuple[int, int]:
    copied = skipped = 0
    for st in statuses:
        if st.state == "UNCHANGED":
            skipped += 1
        else:
            st.dst.parent.mkdir(parents=True, exist_ok=True)
            if _is_settings_json(st.src):
                st.dst.write_text(_effective_settings_text(st.src), encoding="utf-8")
                shutil.copystat(st.src, st.dst)
            else:
                shutil.copy2(st.src, st.dst)
            copied += 1
    return copied, skipped


def backup_settings() -> Path | None:
    src = TARGET / "settings.json"
    if not src.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = TARGET / f"settings.json.bak.{ts}"
    shutil.copy2(src, dst)
    return dst


def prune_backups(keep: int = 10) -> None:
    baks = sorted(TARGET.glob("settings.json.bak*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in baks[keep:]:
        old.unlink(missing_ok=True)
