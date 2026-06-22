"""Graph snapshot generation for OKF bundles."""

from __future__ import annotations

from collections import Counter
from typing import Any

from cabal.okf.models import ConceptDocument, DoctorFinding, Relation


def build_graph(
    concepts: tuple[ConceptDocument, ...],
    relations: tuple[Relation, ...],
    *,
    generated_at: str,
    findings: tuple[DoctorFinding, ...] = (),
) -> dict[str, Any]:
    nodes = sorted((concept.to_node() for concept in concepts), key=lambda item: (item["type"], item["id"]))
    edges = sorted(
        (relation.to_graph_edge() for relation in relations),
        key=lambda item: (item["kind"], item["source"], item["target_ref"], item["id"]),
    )
    node_counts = Counter(node["type"] for node in nodes)
    edge_counts = Counter(edge["kind"] for edge in edges)
    finding_counts = Counter(finding.severity for finding in findings)
    return {
        "schema_version": "1",
        "bundle_id": "prompt-lib",
        "generated_at": generated_at,
        "nodes": nodes,
        "edges": edges,
        "counts": {
            "nodes_by_type": dict(sorted(node_counts.items())),
            "edges_by_kind": dict(sorted(edge_counts.items())),
            "findings_by_severity": dict(sorted(finding_counts.items())),
        },
        "findings": [finding.to_dict() for finding in findings],
    }
