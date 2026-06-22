from __future__ import annotations

from pathlib import Path

from cabal.okf.exporter import build_concepts
from cabal.okf.relations import derive_backlinks, extract_relations, resolve_relations
from cabal.okf.sources import discover_sources


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
FIXED_TIME = "2026-06-18T00:00:00Z"


def _relations():
    concepts = build_concepts(discover_sources(FIXTURE_REPO), FIXED_TIME)
    relations = resolve_relations(extract_relations(FIXTURE_REPO, concepts), concepts)
    return concepts, relations


def test_extracts_explicit_agent_tokens() -> None:
    _, relations = _relations()

    edge = next(
        relation
        for relation in relations
        if relation.source_id == "skill:orchestrate"
        and relation.target_id == "agent:python-architect"
    )

    assert edge.kind == "routes_to"
    assert edge.confidence == "explicit"
    assert edge.evidence[0].line is not None


def test_extracts_routing_table_edges_and_backlinks() -> None:
    concepts, relations = _relations()
    backlinks = derive_backlinks(concepts, relations)

    assert any(
        relation.target_id == "agent:python-tester"
        and relation.confidence == "structured"
        for relation in relations
    )
    assert "agent:python-tester" in backlinks
    assert any(link.source_id == "skill:orchestrate" for link in backlinks["agent:python-tester"])


def test_unresolved_agent_reference_is_preserved() -> None:
    _, relations = _relations()

    unresolved = next(
        relation for relation in relations if relation.target_ref == "@missing-agent"
    )

    assert unresolved.target_id is None
    assert unresolved.target_ref == "@missing-agent"
