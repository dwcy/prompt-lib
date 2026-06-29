# -*- coding: utf-8 -*-
"""Tests for OKF runtime roots, structural relations, and isolated-node detection."""

from __future__ import annotations

import json
from pathlib import Path

from cabal.okf.doctor import find_isolated_nodes
from cabal.okf.models import ConceptDocument
from cabal.okf.structure import (
    CLAUDE_ROOT_ID,
    CODEX_ROOT_ID,
    PROJECT_ROOT_ID,
    build_root_concepts,
    extract_structural_relations,
)


def _concept(concept_id: str, doc_type: str, resource: str) -> ConceptDocument:
    return ConceptDocument(
        id=concept_id,
        type=doc_type,
        title=concept_id.split(":", 1)[-1],
        description="x",
        resource=resource,
        tags=("prompt-lib", doc_type),
        timestamp="2026-06-30T00:00:00Z",
        path=f"{doc_type}/{concept_id.split(':', 1)[-1]}.md",
        body="x\n",
    )


def _sample_concepts() -> tuple[ConceptDocument, ...]:
    return build_root_concepts("2026-06-30T00:00:00Z") + (
        _concept("agent:api-designer", "agent", "global/agents/api-designer.md"),
        _concept("skill:add-mcp", "skill", "global/skills/add-mcp.md"),
        _concept("codex:add-mcp", "codex", "global/codex/skills/add-mcp/SKILL.md"),
        _concept("codex:run", "codex", "global/codex/skills/add-mcp/scripts/run.py"),
        _concept("tool:tools", "tool", "setup/src/cabal/tools.py"),
        _concept("spec:demo", "spec", "specs/001-demo/spec.md"),
    )


def test_build_root_concepts_returns_project_and_two_runtimes():
    roots = build_root_concepts("2026-06-30T00:00:00Z")

    ids = {concept.id: concept.type for concept in roots}

    assert ids == {
        PROJECT_ROOT_ID: "project",
        CLAUDE_ROOT_ID: "runtime",
        CODEX_ROOT_ID: "runtime",
    }


def test_every_non_root_concept_gets_an_incoming_edge(tmp_path: Path):
    concepts = _sample_concepts()

    relations = extract_structural_relations(tmp_path, concepts)

    targets = {relation.target_id for relation in relations}
    non_roots = {
        concept.id
        for concept in concepts
        if concept.id not in {PROJECT_ROOT_ID, CLAUDE_ROOT_ID, CODEX_ROOT_ID}
    }
    assert non_roots <= targets


def test_project_contains_both_runtimes(tmp_path: Path):
    concepts = _sample_concepts()

    relations = extract_structural_relations(tmp_path, concepts)

    contained = {
        relation.target_id
        for relation in relations
        if relation.source_id == PROJECT_ROOT_ID and relation.kind == "contains"
    }
    assert {CLAUDE_ROOT_ID, CODEX_ROOT_ID} <= contained


def test_skill_asset_is_contained_by_its_skill_not_the_runtime(tmp_path: Path):
    concepts = _sample_concepts()

    relations = extract_structural_relations(tmp_path, concepts)

    asset_edges = [rel for rel in relations if rel.target_id == "codex:run"]

    assert len(asset_edges) == 1
    assert asset_edges[0].kind == "contains"
    assert asset_edges[0].source_id == "codex:add-mcp"


def test_runtime_provides_top_level_capability(tmp_path: Path):
    concepts = _sample_concepts()

    relations = extract_structural_relations(tmp_path, concepts)

    provides = {
        (rel.source_id, rel.target_id) for rel in relations if rel.kind == "provides"
    }
    assert (CLAUDE_ROOT_ID, "agent:api-designer") in provides
    assert (CODEX_ROOT_ID, "codex:add-mcp") in provides


def test_mirrors_edge_links_codex_artifact_to_claude_source(tmp_path: Path):
    manifest = tmp_path / "global" / "codex" / "conversion-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "source": "global/skills/add-mcp.md",
                        "output": "global/codex/skills/add-mcp/SKILL.md",
                        "kind": "skill",
                        "status": "converted",
                    },
                    {
                        "source": "global/hooks/",
                        "output": None,
                        "kind": "unsupported",
                        "status": "unsupported",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    relations = extract_structural_relations(tmp_path, _sample_concepts())

    mirrors = [rel for rel in relations if rel.kind == "mirrors"]

    assert len(mirrors) == 1
    assert mirrors[0].source_id == "codex:add-mcp"
    assert mirrors[0].target_id == "skill:add-mcp"


def test_find_isolated_nodes_reports_unlinked_only():
    node_ids = {"a", "b", "c", "d"}
    edges = [{"source": "a", "target": "b"}, {"source": "c", "target": None}]

    assert find_isolated_nodes(node_ids, edges) == ["d"]
