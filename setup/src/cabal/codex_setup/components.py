# -*- coding: utf-8 -*-
"""Component registry for global/codex -> ~/.codex deployment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cabal.codex_setup.paths import CODEX_PROMPTLIB_TARGET, CODEX_SOURCE_DIR, CODEX_TARGET
from cabal.os_filters import _os_should_skip


@dataclass
class CodexComponent:
    key: str
    label: str
    type: str
    src: str
    dst: str
    glob: str = "*"
    recursive: bool = False

    @property
    def src_path(self) -> Path:
        return CODEX_SOURCE_DIR / self.src

    @property
    def dst_path(self) -> Path:
        if self.dst.startswith("prompt-lib/"):
            return CODEX_PROMPTLIB_TARGET / self.dst.removeprefix("prompt-lib/")
        return CODEX_TARGET / self.dst

    def list_files(self) -> list[tuple[Path, Path]]:
        if not self.src_path.exists():
            return []
        if self.type == "file":
            if _os_should_skip(self.src_path.name):
                return []
            return [(self.src_path, Path(self.dst).name)]

        iterator = (
            self.src_path.rglob("*")
            if self.recursive
            else self.src_path.glob(self.glob)
        )
        out: list[tuple[Path, Path]] = []
        for f in iterator:
            if not f.is_file() or _os_should_skip(f.name):
                continue
            out.append((f, f.relative_to(self.src_path)))
        return out


CODEX_COMPONENTS: list[CodexComponent] = [
    CodexComponent("skills", "skills/", "dir", "skills", "skills", recursive=True),
    CodexComponent(
        "references",
        "prompt-lib/references/",
        "dir",
        "references",
        "prompt-lib/references",
        recursive=True,
    ),
    CodexComponent(
        "project_templates",
        "prompt-lib/project-templates/",
        "dir",
        "project-templates",
        "prompt-lib/project-templates",
        recursive=True,
    ),
    CodexComponent(
        "readme",
        "prompt-lib/README.md",
        "file",
        "README.md",
        "prompt-lib/README.md",
    ),
    CodexComponent(
        "manifest",
        "prompt-lib/conversion-manifest.json",
        "file",
        "conversion-manifest.json",
        "prompt-lib/conversion-manifest.json",
    ),
    CodexComponent(
        "statusline_metadata",
        "prompt-lib/statusline-segments.json",
        "file",
        "statusline-segments.json",
        "prompt-lib/statusline-segments.json",
    ),
]
