from __future__ import annotations

from pathlib import Path
import re

from cabal.okf.exporter import export_okf
from cabal.okf.viewer import generate_viewer


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"


def test_static_graph_viewer_embeds_graph_json(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    export_okf(FIXTURE_REPO, out, generated_at="2026-06-18T00:00:00Z")

    viewer = generate_viewer(out / "graph.json", out / "graph.html")
    html = viewer.read_text(encoding="utf-8")

    assert "graph-data" in html
    assert "node-link-map" in html
    assert "Route map" in html
    assert "Inspector" in html
    assert "routes_to" in html
    assert "skill:orchestrate" in html
    graph_data = re.search(
        r'<script type="application/json" id="graph-data">(.*?)</script>',
        html,
        re.S,
    )
    assert graph_data is not None
    assert "&quot;" not in graph_data.group(1)
