# -*- coding: utf-8 -*-
"""Init Project file staging — `InjectableFile`, safe-extract validator, template enumeration, Apply step.

Consumed by `cabal.views.init_project` (the InitProjectScreen Apply step).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from cabal.claude_cli import ClaudeRunResult


_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


@dataclass
class LocalTemplateRef:
    """A CLAUDE.md template shipped under `global/project-templates/`."""

    stem: str
    path: Path
    gitignore_preset_name: str | None = None


@dataclass
class InjectableFile:
    """One file (or scaffold dir) the Apply step will write into the target project."""

    source_path: Path
    dest_relpath: PurePosixPath
    size_bytes: int
    selected: bool = True
    status: str = "NEW"
    origin: str = "github"

    def __post_init__(self) -> None:
        p = self.dest_relpath
        if p.is_absolute():
            raise ValueError(f"dest_relpath must be relative: {p}")
        if any(part == ".." for part in p.parts):
            raise ValueError(f"dest_relpath must not contain '..': {p}")


@dataclass
class ApplyReport:
    """Outcome of `apply_plan` plus the gitignore / MCP / claude post-steps."""

    target_dir: Path
    files_written: int
    bytes_written: int
    mcp_entries: int = 0
    gitignore_added: bool = False
    gitignore_already_tracked: bool = False
    claude_run: ClaudeRunResult | None = None
    error: str | None = None


class UnsafeArchiveError(RuntimeError):
    """Raised when a tarball contains a path that would escape the extraction root."""


def _validate_safe(tar: tarfile.TarFile) -> None:
    """Reject the archive on absolute paths, `..` segments, links, or Windows drive prefixes."""
    for member in tar.getmembers():
        name = member.name
        normalized = name.replace("\\", "/")

        if normalized.startswith("/") or name.startswith("\\") or _WINDOWS_DRIVE_RE.match(name):
            raise UnsafeArchiveError(f"unsafe path in archive: {name}")
        if any(part == ".." for part in PurePosixPath(normalized).parts):
            raise UnsafeArchiveError(f"unsafe path in archive: {name}")
        if member.issym() or member.islnk():
            raise UnsafeArchiveError(f"unsafe path in archive: {name}")


def enumerate_local_template_files(
    template: LocalTemplateRef,
    scaffold_dir_relpaths: list[str] | None = None,
) -> list[InjectableFile]:
    """Return the CLAUDE.md row plus optional scaffold-dir rows for a local template."""
    rows: list[InjectableFile] = [
        InjectableFile(
            source_path=template.path,
            dest_relpath=PurePosixPath("CLAUDE.md"),
            size_bytes=template.path.stat().st_size,
            selected=True,
            status="NEW",
            origin="local-template",
        )
    ]
    for rel in scaffold_dir_relpaths or []:
        rows.append(InjectableFile(
            source_path=Path(""),
            dest_relpath=PurePosixPath(rel),
            size_bytes=0,
            selected=True,
            status="NEW",
            origin="scaffold",
        ))
    return rows


def enumerate_github_template_files(extract_dir: Path) -> list[InjectableFile]:
    """Walk a freshly extracted GitHub tarball and produce one `InjectableFile` per file."""
    children = [c for c in extract_dir.iterdir() if c.is_dir()]
    root = children[0] if len(children) == 1 else extract_dir

    rows: list[InjectableFile] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        rel_posix = PurePosixPath(*rel.parts)
        if any(part == ".git" for part in rel_posix.parts):
            continue
        rows.append(InjectableFile(
            source_path=p,
            dest_relpath=rel_posix,
            size_bytes=p.stat().st_size,
            origin="github",
        ))
    rows.sort(key=lambda r: str(r.dest_relpath))
    return rows


def apply_plan(
    target_dir: Path,
    injectables: list[InjectableFile],
) -> ApplyReport:
    """Create target_dir + write every selected InjectableFile. Path traversal guard per I-5."""
    target_dir.mkdir(parents=True, exist_ok=True)
    target_abs = target_dir.resolve()
    bytes_written = 0
    files_written = 0
    for inj in injectables:
        if not inj.selected:
            continue
        dest = (target_abs / Path(str(inj.dest_relpath))).resolve()
        dest.relative_to(target_abs)
        if inj.origin == "scaffold":
            if str(inj.dest_relpath).endswith("settings.local.json"):
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    dest.write_text(
                        '{\n  "permissions": {\n    "allow": []\n  }\n}\n',
                        encoding="utf-8",
                    )
            else:
                dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(inj.source_path, dest)
        bytes_written += inj.size_bytes
        files_written += 1
    return ApplyReport(
        target_dir=target_dir,
        files_written=files_written,
        bytes_written=bytes_written,
    )


def count_project_mcp_entries(target_dir: Path) -> int:
    """Return the number of entries under `mcpServers` in `<target>/.mcp.json`, or 0 if absent/invalid."""
    p = target_dir / ".mcp.json"
    if not p.exists():
        return 0
    try:
        return len((json.loads(p.read_text(encoding="utf-8")).get("mcpServers") or {}))
    except Exception:
        return 0


def ensure_mcp_gitignored(target_dir: Path) -> tuple[bool, bool]:
    """Append `.mcp.json` to `<target>/.gitignore` (idempotent) + report whether it's already git-tracked."""
    needle = ".mcp.json"
    gi = target_dir / ".gitignore"
    added = False
    if not gi.exists():
        gi.write_text(needle + "\n", encoding="utf-8")
        added = True
    else:
        lines = gi.read_text(encoding="utf-8").splitlines()
        if needle not in [ln.strip() for ln in lines]:
            sep = "" if (lines and lines[-1] == "") else "\n"
            with gi.open("a", encoding="utf-8") as f:
                f.write(sep + needle + "\n")
            added = True
    already_tracked = False
    if shutil.which("git"):
        r = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".mcp.json"],
            cwd=str(target_dir), capture_output=True, text=True, check=False,
        )
        if r.returncode == 0:
            already_tracked = True
    return added, already_tracked
