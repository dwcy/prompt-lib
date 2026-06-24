from __future__ import annotations

import json
from pathlib import Path

from cabal.okf.exporter import export_okf


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
FIXED_TIME = "2026-06-18T00:00:00Z"


def test_graph_json_contract_shape_and_counts(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    export_okf(FIXTURE_REPO, out, generated_at=FIXED_TIME)

    graph = json.loads((out / "graph.json").read_text(encoding="utf-8"))

    assert graph["schema_version"] == "1"
    assert graph["bundle_id"] == "prompt-lib"
    assert graph["counts"]["nodes_by_type"]["agent"] == 3
    assert any(node["id"] == "skill:orchestrate" for node in graph["nodes"])


def test_graph_json_contract_routes_to_edges_with_evidence(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    export_okf(FIXTURE_REPO, out, generated_at=FIXED_TIME)
    graph = json.loads((out / "graph.json").read_text(encoding="utf-8"))

    edge = next(
        edge
        for edge in graph["edges"]
        if edge["source"] == "skill:orchestrate"
        and edge["target"] == "agent:python-architect"
    )

    assert edge["kind"] == "routes_to"
    assert edge["confidence"] == "explicit"
    assert edge["evidence"][0]["resource"] == "global/skills/orchestrate.md"
