# -*- coding: utf-8 -*-
"""Diff/apply helpers for global/codex -> ~/.codex."""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

from cabal.components import FileStatus
from cabal.codex_setup.components import CODEX_COMPONENTS, CodexComponent
from cabal.codex_setup.paths import CODEX_TARGET


def diff_codex_component(comp: CodexComponent) -> list[FileStatus]:
    out: list[FileStatus] = []
    for src_file, rel in comp.list_files():
        dst_file = comp.dst_path / rel if comp.type == "dir" else comp.dst_path
        if not dst_file.exists():
            out.append(FileStatus(rel, src_file, dst_file, "NEW"))
        elif filecmp.cmp(src_file, dst_file, shallow=False):
            out.append(FileStatus(rel, src_file, dst_file, "UNCHANGED"))
        else:
            out.append(FileStatus(rel, src_file, dst_file, "CHANGED"))
    return out


def find_codex_extras(comp: CodexComponent) -> list[Path]:
    if comp.type == "file" or not comp.dst_path.exists():
        return []
    src_rels = {rel for _, rel in comp.list_files()}
    iterator = comp.dst_path.rglob("*") if comp.recursive else comp.dst_path.glob(comp.glob)
    return [
        f.relative_to(comp.dst_path)
        for f in iterator
        if f.is_file() and f.relative_to(comp.dst_path) not in src_rels
    ]


def has_codex_deploy_drift() -> bool:
    for comp in CODEX_COMPONENTS:
        if not comp.src_path.exists():
            continue
        if any(st.state in ("NEW", "CHANGED") for st in diff_codex_component(comp)):
            return True
    return False


def apply_codex_statuses(statuses: list[FileStatus]) -> tuple[int, int]:
    copied = skipped = 0
    for st in statuses:
        if st.state == "UNCHANGED":
            skipped += 1
            continue
        st.dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(st.src, st.dst)
        copied += 1
    return copied, skipped


def ensure_codex_target() -> None:
    CODEX_TARGET.mkdir(parents=True, exist_ok=True)
