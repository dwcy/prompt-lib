"""Relation extraction for prompt-lib OKF concepts."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from cabal.okf.models import Backlink, ConceptDocument, EdgeEvidence, Relation
from cabal.okf.paths import resource_path


AGENT_TOKEN_RE = re.compile(r"@([a-z][a-z0-9-]+)")
_PLACEHOLDER_TOKENS = {"agent", "agent-name", "user", "auth"}
_AGENT_LIKE_SUFFIXES = (
    "-agent",
    "-architect",
    "-tester",
    "-analyst",
    "-auditor",
    "-designer",
    "-manager",
    "-verifier",
    "-css",
)


def relation_id(source_id: str, kind: str, target_ref: str) -> str:
    digest = hashlib.sha1(f"{source_id}|{kind}|{target_ref}".encode("utf-8")).hexdigest()[:10]
    safe_target = target_ref.removeprefix("@").replace("/", "-")
    return f"edge:{source_id}:{kind}:{safe_target}:{digest}"


def _relation(
    *,
    source_id: str,
    target_ref: str,
    confidence: str,
    reason: str,
    evidence: EdgeEvidence,
) -> Relation:
    return Relation(
        id=relation_id(source_id, "routes_to", target_ref),
        kind="routes_to",
        source_id=source_id,
        target_ref=target_ref,
        confidence=confidence,
        reason=reason,
        evidence=(evidence,),
    )


def _agent_target_ref(value: str) -> str:
    value = value.strip().strip("`").strip()
    return value if value.startswith("@") else f"@{value}"


def _looks_like_agent(name: str, known_names: set[str]) -> bool:
    if name in _PLACEHOLDER_TOKENS:
        return False
    return name in known_names or any(name.endswith(suffix) for suffix in _AGENT_LIKE_SUFFIXES)


def _extract_table_agent(row: str, known_names: set[str]) -> str | None:
    if "|" not in row or "---" in row:
        return None
    cells = [cell.strip().strip("`") for cell in row.strip().strip("|").split("|")]
    for cell in cells:
        normalized = cell.removeprefix("@")
        if _looks_like_agent(normalized, known_names):
            return _agent_target_ref(normalized)
    return None


def extract_relations(
    repo_root: Path,
    concepts: tuple[ConceptDocument, ...],
) -> tuple[Relation, ...]:
    agent_names = {
        concept.id.removeprefix("agent:")
        for concept in concepts
        if concept.type == "agent"
    }
    skill_concepts = [concept for concept in concepts if concept.type == "skill"]
    merged: dict[tuple[str, str], Relation] = {}

    for concept in skill_concepts:
        source_path = resource_path(repo_root, concept.resource)
        if not source_path.exists():
            continue
        lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for idx, line in enumerate(lines, start=1):
            for match in AGENT_TOKEN_RE.finditer(line):
                agent_name = match.group(1)
                if not _looks_like_agent(agent_name, agent_names):
                    continue
                target_ref = f"@{agent_name}"
                evidence = EdgeEvidence(
                    resource=concept.resource,
                    line=idx,
                    text=match.group(0),
                    extractor="agent_token",
                )
                rel = _relation(
                    source_id=concept.id,
                    target_ref=target_ref,
                    confidence="explicit",
                    reason=f"Skill references {target_ref}.",
                    evidence=evidence,
                )
                merged[(rel.source_id, rel.target_ref)] = rel

            table_ref = _extract_table_agent(line, agent_names)
            if table_ref:
                cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
                evidence = EdgeEvidence(
                    resource=concept.resource,
                    line=idx,
                    text=" | ".join(cells),
                    extractor="routing_table",
                )
                reason = cells[-1] if cells else f"Skill routing table selects {table_ref}."
                rel = _relation(
                    source_id=concept.id,
                    target_ref=table_ref,
                    confidence="structured",
                    reason=reason,
                    evidence=evidence,
                )
                key = (rel.source_id, rel.target_ref)
                existing = merged.get(key)
                if existing:
                    combined = replace(
                        existing,
                        confidence="structured" if existing.confidence != "explicit" else existing.confidence,
                        evidence=existing.evidence + rel.evidence,
                    )
                    merged[key] = combined
                else:
                    merged[key] = rel

    return tuple(sorted(merged.values(), key=lambda item: (item.source_id, item.target_ref)))


def resolve_relations(
    relations: tuple[Relation, ...],
    concepts: tuple[ConceptDocument, ...],
) -> tuple[Relation, ...]:
    by_agent_name = {
        concept.id.removeprefix("agent:"): concept
        for concept in concepts
        if concept.type == "agent"
    }
    resolved: list[Relation] = []
    for relation in relations:
        target_name = relation.target_ref.removeprefix("@")
        target = by_agent_name.get(target_name)
        if target:
            resolved.append(
                replace(
                    relation,
                    target_id=target.id,
                    target_resource=target.resource,
                )
            )
        else:
            resolved.append(relation)
    return tuple(resolved)


def derive_backlinks(
    concepts: tuple[ConceptDocument, ...],
    relations: tuple[Relation, ...],
) -> dict[str, tuple[Backlink, ...]]:
    titles = {concept.id: concept.title for concept in concepts}
    grouped: dict[str, list[Backlink]] = defaultdict(list)
    for relation in relations:
        if not relation.target_id:
            continue
        grouped[relation.target_id].append(
            Backlink(
                source_id=relation.source_id,
                source_title=titles.get(relation.source_id, relation.source_id),
                kind=relation.kind,
                reason=relation.reason,
                evidence=relation.evidence,
            )
        )
    return {
        key: tuple(sorted(value, key=lambda link: (link.kind, link.source_id)))
        for key, value in grouped.items()
    }


def attach_relations(
    concepts: tuple[ConceptDocument, ...],
    relations: tuple[Relation, ...],
) -> tuple[ConceptDocument, ...]:
    outgoing: dict[str, list[Relation]] = defaultdict(list)
    for relation in relations:
        outgoing[relation.source_id].append(relation)
    backlinks = derive_backlinks(concepts, relations)
    updated = [
        concept.with_relations(
            relations=tuple(sorted(outgoing.get(concept.id, ()), key=lambda item: item.id)),
            backlinks=backlinks.get(concept.id, ()),
        )
        for concept in concepts
    ]
    return tuple(updated)
