"""Structural relations and runtime roots for the prompt-lib OKF graph.

Connects otherwise-isolated concept nodes by modelling ownership: a project
root contains the two runtimes (Claude, Codex); each runtime *provides* its
capabilities (agents, skills, hooks, rules, output styles, templates); skill
folders *contain* their nested assets; and each Codex artifact *mirrors* the
Claude source it was converted from (read from the conversion manifest).
"""

from __future__ import annotations

import json
from pathlib import Path

from cabal.okf.models import ConceptDocument, EdgeEvidence, Relation
from cabal.okf.paths import resource_path
from cabal.okf.relations import relation_id


PROJECT_ROOT_ID = "project:prompt-lib"
CLAUDE_ROOT_ID = "runtime:claude"
CODEX_ROOT_ID = "runtime:codex"

_CONVERSION_MANIFEST = "global/codex/conversion-manifest.json"
_CLAUDE_PREFIX = "global/"
_CODEX_PREFIX = "global/codex/"
_SKILL_MARKER = "/SKILL.md"

_ROOT_SPECS: tuple[tuple[str, str, str, str, str, str], ...] = (
    (
        PROJECT_ROOT_ID,
        "project",
        "prompt-lib",
        "CLAUDE.md",
        "roots/project-prompt-lib.md",
        "Root of the prompt-lib configuration library; owns the Claude and Codex runtimes.",
    ),
    (
        CLAUDE_ROOT_ID,
        "runtime",
        "Claude",
        "global/CLAUDE.md",
        "roots/runtime-claude.md",
        "Claude Code runtime; provides agents, skills, hooks, rules, output styles, and templates.",
    ),
    (
        CODEX_ROOT_ID,
        "runtime",
        "Codex",
        _CONVERSION_MANIFEST,
        "roots/runtime-codex.md",
        "Codex runtime; provides the skills, rules, and output styles converted from Claude sources.",
    ),
)


def _root_body(title: str, description: str, resource: str) -> str:
    lines = [f"# {title}", "", description, "", f"- Source: `{resource}`", "- Category: `root`"]
    return "\n".join(lines) + "\n"


def build_root_concepts(generated_at: str) -> tuple[ConceptDocument, ...]:
    concepts: list[ConceptDocument] = []
    for concept_id, doc_type, title, resource, path, description in _ROOT_SPECS:
        concepts.append(
            ConceptDocument(
                id=concept_id,
                type=doc_type,
                title=title,
                description=description,
                resource=resource,
                tags=("prompt-lib", doc_type, "root"),
                timestamp=generated_at,
                path=path,
                body=_root_body(title, description, resource),
            )
        )
    return tuple(concepts)


def _relation(
    *,
    kind: str,
    source: ConceptDocument,
    target: ConceptDocument,
    reason: str,
    extractor: str,
    evidence_resource: str,
) -> Relation:
    evidence = EdgeEvidence(resource=evidence_resource, text=reason, extractor=extractor)
    return Relation(
        id=relation_id(source.id, kind, target.id),
        kind=kind,
        source_id=source.id,
        target_ref=target.id,
        target_id=target.id,
        target_resource=target.resource,
        confidence="structured",
        reason=reason,
        evidence=(evidence,),
    )


def _skill_folders(concepts: tuple[ConceptDocument, ...]) -> dict[str, ConceptDocument]:
    folders: dict[str, ConceptDocument] = {}
    for concept in concepts:
        if concept.resource.endswith(_SKILL_MARKER):
            folders[concept.resource[: -len(_SKILL_MARKER)]] = concept
    return folders


def _owning_skill(resource: str, folders: dict[str, ConceptDocument]) -> ConceptDocument | None:
    candidates = [
        folder
        for prefix, folder in folders.items()
        if resource.startswith(prefix + "/") and resource != folder.resource
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda concept: len(concept.resource))


def _ownership_relations(
    concepts: tuple[ConceptDocument, ...],
    roots: dict[str, ConceptDocument],
) -> list[Relation]:
    folders = _skill_folders(concepts)
    relations: list[Relation] = []
    for concept in concepts:
        if concept.id in roots:
            continue
        skill = _owning_skill(concept.resource, folders)
        if skill is not None:
            relations.append(
                _relation(
                    kind="contains",
                    source=skill,
                    target=concept,
                    reason=f"{skill.title} skill folder contains this asset.",
                    extractor="skill_asset",
                    evidence_resource=skill.resource,
                )
            )
            continue
        if concept.resource.startswith(_CODEX_PREFIX):
            runtime = roots[CODEX_ROOT_ID]
        elif concept.resource.startswith(_CLAUDE_PREFIX):
            runtime = roots[CLAUDE_ROOT_ID]
        else:
            relations.append(
                _relation(
                    kind="contains",
                    source=roots[PROJECT_ROOT_ID],
                    target=concept,
                    reason="prompt-lib project contains this artifact.",
                    extractor="project_member",
                    evidence_resource=concept.resource,
                )
            )
            continue
        relations.append(
            _relation(
                kind="provides",
                source=runtime,
                target=concept,
                reason=f"{runtime.title} runtime provides this {concept.type}.",
                extractor="runtime_capability",
                evidence_resource=concept.resource,
            )
        )
    return relations


def _mirror_relations(
    repo_root: Path,
    by_resource: dict[str, ConceptDocument],
) -> list[Relation]:
    manifest_path = resource_path(repo_root, _CONVERSION_MANIFEST)
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    relations: list[Relation] = []
    for entry in manifest.get("entries", []):
        if entry.get("status") != "converted":
            continue
        source = by_resource.get(str(entry.get("source") or ""))
        output = by_resource.get(str(entry.get("output") or ""))
        if source is None or output is None:
            continue
        relations.append(
            _relation(
                kind="mirrors",
                source=output,
                target=source,
                reason=f"Codex {entry.get('kind', 'artifact')} converted from {source.resource}.",
                extractor="conversion_manifest",
                evidence_resource=_CONVERSION_MANIFEST,
            )
        )
    return relations


def extract_structural_relations(
    repo_root: Path,
    concepts: tuple[ConceptDocument, ...],
) -> tuple[Relation, ...]:
    roots = {
        concept.id: concept
        for concept in concepts
        if concept.id in {PROJECT_ROOT_ID, CLAUDE_ROOT_ID, CODEX_ROOT_ID}
    }
    by_resource = {concept.resource: concept for concept in concepts}
    relations: list[Relation] = []
    if PROJECT_ROOT_ID in roots:
        for runtime_id in (CLAUDE_ROOT_ID, CODEX_ROOT_ID):
            runtime = roots.get(runtime_id)
            if runtime is not None:
                relations.append(
                    _relation(
                        kind="contains",
                        source=roots[PROJECT_ROOT_ID],
                        target=runtime,
                        reason=f"prompt-lib project contains the {runtime.title} runtime.",
                        extractor="project_member",
                        evidence_resource=runtime.resource,
                    )
                )
    relations.extend(_ownership_relations(concepts, roots))
    relations.extend(_mirror_relations(repo_root, by_resource))
    return tuple(sorted(relations, key=lambda item: (item.kind, item.source_id, item.target_ref)))
