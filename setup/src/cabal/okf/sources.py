"""Source discovery for prompt-lib OKF export."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from cabal.okf.models import SourceArtifact
from cabal.okf.paths import to_resource


CATEGORY_DIRS: tuple[tuple[str, str], ...] = (
    ("agent", "global/agents"),
    ("skill", "global/skills"),
    ("hook", "global/hooks"),
    ("rule", "global/rules"),
    ("output_style", "global/output-styles"),
    ("template", "global/project-templates"),
    ("codex", "global/codex"),
    ("spec", "specs"),
)

TOOL_FILES: tuple[str, ...] = (
    "setup/src/cabal/tools.py",
    "setup/mcp-templates.json",
)
TOOL_DIRS: tuple[str, ...] = ("setup/src/cabal/installers",)


def _iter_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(
        (
            child
            for child in path.rglob("*")
            if child.is_file() and "__pycache__" not in child.parts
        ),
        key=lambda item: item.as_posix().lower(),
    )


def _name_for(category: str, resource: str) -> str:
    path = Path(resource)
    if path.name.upper() == "SKILL.md":
        return path.parent.name
    if category == "spec":
        return resource.removesuffix(".md").replace("/", "-")
    return path.stem


def discover_sources(repo_root: Path) -> tuple[SourceArtifact, ...]:
    repo_root = Path(repo_root)
    sources: list[SourceArtifact] = []
    seen: set[str] = set()

    for category, rel_dir in CATEGORY_DIRS:
        for path in _iter_files(repo_root / rel_dir):
            resource = to_resource(repo_root, path)
            if resource in seen:
                continue
            seen.add(resource)
            sources.append(
                SourceArtifact(
                    resource=resource,
                    category=category,
                    name=_name_for(category, resource),
                )
            )

    for rel in TOOL_FILES:
        path = repo_root / rel
        if path.exists():
            resource = to_resource(repo_root, path)
            if resource not in seen:
                seen.add(resource)
                sources.append(SourceArtifact(resource=resource, category="tool", name=path.stem))

    for rel_dir in TOOL_DIRS:
        for path in _iter_files(repo_root / rel_dir):
            resource = to_resource(repo_root, path)
            if resource in seen:
                continue
            seen.add(resource)
            sources.append(SourceArtifact(resource=resource, category="tool", name=path.stem))

    return tuple(sorted(sources, key=lambda item: (item.category, item.resource.lower())))


def count_by_category(sources: tuple[SourceArtifact, ...]) -> dict[str, int]:
    counts = Counter(source.category for source in sources)
    return dict(sorted(counts.items()))
