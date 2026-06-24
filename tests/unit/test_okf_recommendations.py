from __future__ import annotations

from pathlib import Path

from cabal.okf.exporter import export_okf
from cabal.okf.recommendations import recommend_from_graph


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
FIXED_TIME = "2026-06-18T00:00:00Z"


def test_recommendation_cites_graph_evidence(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    export_okf(FIXTURE_REPO, out, generated_at=FIXED_TIME)

    recommendations = recommend_from_graph(
        out / "graph.json",
        "design a Python service architecture",
    )

    assert recommendations
    assert recommendations[0]["target"] == "agent:python-architect"
    assert recommendations[0]["evidence"]
