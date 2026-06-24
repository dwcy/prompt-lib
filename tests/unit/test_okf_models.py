from __future__ import annotations

from cabal.okf.models import ConceptDocument, EdgeEvidence, Relation, SourceArtifact


def test_source_artifact_and_concept_models_are_constructible() -> None:
    artifact = SourceArtifact(
        resource="global/agents/python-architect.md",
        category="agent",
        name="python-architect",
    )
    concept = ConceptDocument(
        id="agent:python-architect",
        type="agent",
        title="python-architect",
        description="Designs Python services.",
        resource=artifact.resource,
        tags=("prompt-lib", "agent"),
        timestamp="2026-06-18T00:00:00Z",
        path="agents/python-architect.md",
        body="# python-architect",
    )

    assert artifact.exists is True
    assert concept.to_node()["id"] == "agent:python-architect"
    assert concept.to_frontmatter()["resource"] == artifact.resource


def test_relation_model_serializes_evidence() -> None:
    evidence = EdgeEvidence(
        resource="global/skills/orchestrate.md",
        line=4,
        text="@python-architect",
        extractor="agent_token",
    )
    relation = Relation(
        id="edge:1",
        kind="routes_to",
        source_id="skill:orchestrate",
        target_id="agent:python-architect",
        target_ref="@python-architect",
        target_resource="global/agents/python-architect.md",
        confidence="explicit",
        reason="Skill references @python-architect.",
        evidence=(evidence,),
    )

    payload = relation.to_dict()

    assert payload["kind"] == "routes_to"
    assert payload["evidence"][0]["line"] == 4
