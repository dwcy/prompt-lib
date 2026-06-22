from __future__ import annotations

from pathlib import Path

from cabal.okf.analytics import analyze_bundle
from cabal.okf.exporter import export_okf
from cabal.okf.index import build_index, search_index


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
FIXED_TIME = "2026-06-18T00:00:00Z"


def _indexed_bundle(tmp_path: Path):
    bundle = tmp_path / "bundle"
    db = tmp_path / "okf.sqlite"
    export_okf(FIXTURE_REPO, bundle, generated_at=FIXED_TIME)
    build_index(bundle, db)
    return bundle, db


def test_build_index_populates_concepts_edges_and_fts(tmp_path: Path) -> None:
    _, db = _indexed_bundle(tmp_path)

    results = search_index(db, "pytest")

    assert any(result["id"] == "skill:orchestrate" for result in results)


def test_analyze_bundle_reports_route_pressure_and_unused_agents(tmp_path: Path) -> None:
    bundle, db = _indexed_bundle(tmp_path)

    report = analyze_bundle(bundle, db_path=db, incoming_threshold=1, fanout_threshold=2)

    assert any(item["agent"] == "agent:python-tester" for item in report["agents_with_many_routes"])
    assert any(item["skill"] == "skill:orchestrate" for item in report["skills_with_many_routes"])
    assert any(item["agent"] == "agent:frontend-css" for item in report["agents_never_referenced"]) is False


def test_analyze_bundle_reports_graph_and_text_overlap(tmp_path: Path) -> None:
    bundle, db = _indexed_bundle(tmp_path)

    report = analyze_bundle(bundle, db_path=db, overlap_threshold=1)

    assert any("skill:orchestrate" in item["skills"] for item in report["skill_graph_overlap"])
    assert any(item["score"] > 0 for item in report["skill_text_overlap"])


def test_analyze_bundle_detects_changed_concepts_between_indexes(tmp_path: Path) -> None:
    first_bundle, first_db = _indexed_bundle(tmp_path / "first")
    second_bundle = tmp_path / "second" / "bundle"
    second_db = tmp_path / "second" / "okf.sqlite"
    export_okf(FIXTURE_REPO, second_bundle, generated_at=FIXED_TIME)
    doc = second_bundle / "skills" / "orchestrate.md"
    doc.write_text(doc.read_text(encoding="utf-8") + "\nExtra indexed text.\n", encoding="utf-8")
    build_index(second_bundle, second_db)

    report = analyze_bundle(second_bundle, db_path=second_db, previous_db_path=first_db)

    assert "skill:orchestrate" in report["changed_concepts"]
