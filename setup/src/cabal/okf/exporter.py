"""OKF bundle exporter."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from cabal.okf.frontmatter import dump_document, extract_frontmatter
from cabal.okf.graph import build_graph
from cabal.okf.models import ConceptDocument, ExportResult, SourceArtifact
from cabal.okf.paths import has_secret_value, safe_excerpt
from cabal.okf.relations import attach_relations, extract_relations, resolve_relations
from cabal.okf.sources import count_by_category, discover_sources
from cabal.okf.structure import build_root_concepts, extract_structural_relations


CATEGORY_DOC_DIRS = {
    "agent": "agents",
    "skill": "skills",
    "hook": "hooks",
    "rule": "rules",
    "output_style": "output-styles",
    "template": "templates",
    "codex": "codex",
    "spec": "specs",
    "tool": "tools",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def concept_id(category: str, name: str) -> str:
    slug = (
        name.lower()
        .replace("\\", "-")
        .replace("/", "-")
        .replace(" ", "-")
        .removesuffix(".md")
    )
    return f"{category}:{slug}"


def document_path(source: SourceArtifact) -> str:
    folder = CATEGORY_DOC_DIRS.get(source.category, source.category)
    name = source.name.lower().replace(" ", "-").replace("_", "-")
    if source.category == "tool" and source.resource.endswith(".json"):
        name = Path(source.resource).stem
    if source.category == "spec":
        name = source.resource.replace("/", "-").removesuffix(".md")
    return f"{folder}/{name}.md"


def _slug(value: str) -> str:
    return (
        value.lower()
        .replace("\\", "-")
        .replace("/", "-")
        .replace(" ", "-")
        .replace("_", "-")
    )


def _unique(base: str, used: set[str], hint: str) -> str:
    candidate = base
    if candidate in used and hint:
        candidate = f"{base}-{hint}"
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{hint}-{suffix}" if hint else f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _read_source(repo_root: Path, resource: str) -> str:
    path = repo_root / Path(resource)
    if not path.exists() or path.is_dir():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _description_for(source: SourceArtifact, text: str) -> str:
    if has_secret_value(text):
        return f"{source.category.replace('_', ' ').title()} metadata from {source.resource}."
    return safe_excerpt(
        text,
        fallback=f"{source.category.replace('_', ' ').title()} from {source.resource}.",
    )


def _safe_content(text: str) -> str:
    """Redacted source body for search/RAG; empty when the source carries any secret."""
    if has_secret_value(text):
        return ""
    _, body = extract_frontmatter(text)
    return body.strip()


def _body_for(source: SourceArtifact, description: str, content: str) -> str:
    lines = [
        f"# {source.name}",
        "",
        description,
        "",
        f"- Source: `{source.resource}`",
        f"- Category: `{source.category}`",
    ]
    if content:
        lines += ["", "## Content", "", content]
    return "\n".join(lines) + "\n"


def build_concepts(
    sources: tuple[SourceArtifact, ...],
    generated_at: str,
    *,
    repo_root: Path | None = None,
) -> tuple[ConceptDocument, ...]:
    repo_root = repo_root or Path.cwd()
    concepts: list[ConceptDocument] = []
    used_ids: set[str] = set()
    used_paths: set[str] = set()
    for source in sources:
        text = _read_source(repo_root, source.resource)
        description = _description_for(source, text)
        tags = ("prompt-lib", source.category.replace("_", "-"))
        if source.resource.startswith("global/"):
            tags = tags + ("claude-code",)
        hint = _slug(Path(source.resource).parent.name)
        base_id = concept_id(source.category, source.name)
        unique_id = _unique(base_id, used_ids, hint)
        base_path = document_path(source)
        stem, _, ext = base_path.rpartition(".")
        unique_path = _unique(stem, used_paths, hint) + (f".{ext}" if ext else "")
        concepts.append(
            ConceptDocument(
                id=unique_id,
                type=source.category,
                title=source.name,
                description=description,
                resource=source.resource,
                tags=tags,
                timestamp=generated_at,
                path=unique_path,
                body=_body_for(source, description, _safe_content(text)),
            )
        )
    return tuple(sorted(concepts, key=lambda item: (item.type, item.id)))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_document(path: Path, concept: ConceptDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = concept.body
    if concept.backlinks:
        body += "\n## Referenced by\n\n"
        for backlink in concept.backlinks:
            body += f"- `{backlink.source_id}` ({backlink.kind}): {backlink.reason}\n"
    path.write_text(dump_document(concept.to_frontmatter(), body), encoding="utf-8")


def _reserved_doc_metadata(
    *,
    doc_type: str,
    title: str,
    description: str,
    generated_at: str,
    resource: str,
) -> dict[str, object]:
    return {
        "type": doc_type,
        "title": title,
        "description": description,
        "resource": resource,
        "tags": ["prompt-lib", doc_type],
        "timestamp": generated_at,
        "id": f"{doc_type}:prompt-lib",
    }


def _write_reserved_docs(
    out_root: Path,
    generated_at: str,
    sources: tuple[SourceArtifact, ...],
    concepts: tuple[ConceptDocument, ...],
    relations_count: int,
) -> None:
    counts = Counter(concept.type for concept in concepts)
    index_body = [
        "# prompt-lib OKF bundle",
        "",
        f"Generated: `{generated_at}`",
        "",
        "## Counts",
        "",
    ]
    for category, count in sorted(counts.items()):
        index_body.append(f"- `{category}`: {count}")
    index_body.extend(
        [
            "",
            f"- Relations: `{relations_count}`",
            "- Graph: [graph.json](./graph.json)",
            "",
        ]
    )
    (out_root / "index.md").write_text(
        dump_document(
            _reserved_doc_metadata(
                doc_type="index",
                title="prompt-lib OKF bundle",
                description="Generated OKF index for prompt-lib.",
                generated_at=generated_at,
                resource="docs/okf/prompt-lib/index.md",
            ),
            "\n".join(index_body),
        ),
        encoding="utf-8",
    )
    log_body = [
        "# OKF export log",
        "",
        f"- Generated: `{generated_at}`",
        "- Exporter: `cabal.okf`",
        f"- Sources: `{len(sources)}`",
        "- Skipped: `0`",
        "",
    ]
    (out_root / "log.md").write_text(
        dump_document(
            _reserved_doc_metadata(
                doc_type="log",
                title="prompt-lib OKF export log",
                description="Generated OKF export log.",
                generated_at=generated_at,
                resource="docs/okf/prompt-lib/log.md",
            ),
            "\n".join(log_body),
        ),
        encoding="utf-8",
    )


def export_okf(
    repo_root: Path,
    out_root: Path | None = None,
    *,
    generated_at: str | None = None,
) -> ExportResult:
    repo_root = Path(repo_root).resolve()
    out_root = Path(out_root or repo_root / "docs" / "okf" / "prompt-lib").resolve()
    generated_at = generated_at or utc_now()
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    sources = discover_sources(repo_root)
    concepts = build_concepts(sources, generated_at, repo_root=repo_root)
    concepts = tuple(
        sorted(
            concepts + build_root_concepts(generated_at),
            key=lambda item: (item.type, item.id),
        )
    )
    semantic = resolve_relations(extract_relations(repo_root, concepts), concepts)
    structural = extract_structural_relations(repo_root, concepts)
    relations = tuple(semantic) + structural
    concepts = attach_relations(concepts, relations)
    graph = build_graph(concepts, relations, generated_at=generated_at)

    for concept in concepts:
        _write_document(out_root / concept.path, concept)

    _write_reserved_docs(out_root, generated_at, sources, concepts, len(relations))
    _write_json(out_root / "graph.json", graph)

    generated_files = sorted(
        str(path.relative_to(out_root)).replace("\\", "/")
        for path in out_root.rglob("*")
        if path.is_file()
    )
    if "manifest.json" not in generated_files:
        generated_files.append("manifest.json")
        generated_files.sort()
    manifest = {
        "bundle_id": "prompt-lib",
        "okf_version": "0.1",
        "generated_at": generated_at,
        "source_revision": None,
        "source_categories": count_by_category(sources),
        "generated_files": generated_files,
        "skipped": [],
        "tool_version": "unknown",
    }
    _write_json(out_root / "manifest.json", manifest)
    generated_files = sorted(
        str(path.relative_to(out_root)).replace("\\", "/")
        for path in out_root.rglob("*")
        if path.is_file()
    )
    return ExportResult(
        bundle_root=str(out_root),
        generated_files=tuple(generated_files),
        document_count=len(concepts),
        relation_count=len(relations),
        source_categories=count_by_category(sources),
    )
