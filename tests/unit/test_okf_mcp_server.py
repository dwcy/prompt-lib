"""Behavior tests for the okf-rag MCP server tools against a fixture bundle."""

from __future__ import annotations

from pathlib import Path

import pytest

from cabal.okf import mcp_server
from cabal.okf.exporter import export_okf
from cabal.okf.index import build_index
from cabal.okf.semantic import SemanticUnavailableError

FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
FIXED_TIME = "2026-06-18T00:00:00Z"


@pytest.fixture
def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bundle_root = tmp_path / "bundle"
    export_okf(FIXTURE_REPO, bundle_root, generated_at=FIXED_TIME)
    build_index(bundle_root)
    monkeypatch.setenv(mcp_server.BUNDLE_ENV_VAR, str(bundle_root))

    def _unavailable(*_args, **_kwargs):
        raise SemanticUnavailableError("semantic disabled in tests")

    monkeypatch.setattr(mcp_server, "semantic_search", _unavailable)
    return bundle_root


def test_search_returns_indexed_concept_for_keyword_query(bundle: Path) -> None:
    payload = mcp_server.okf_search("pytest")

    assert any(row["id"] == "skill:orchestrate" for row in payload["results"])


def test_search_reports_fresh_index_state(bundle: Path) -> None:
    payload = mcp_server.okf_search("pytest")

    assert payload["index_state"] == "fresh"


def test_search_reports_semantic_unavailable_without_fastembed(bundle: Path) -> None:
    payload = mcp_server.okf_search("pytest")

    assert payload["semantic"] == "unavailable"


def test_search_appends_mcp_usage_ledger_entry(bundle: Path) -> None:
    mcp_server.okf_search("pytest")

    assert (bundle / "usage.jsonl").exists()


def test_search_without_index_returns_rebuild_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_bundle = tmp_path / "empty"
    empty_bundle.mkdir()
    monkeypatch.setenv(mcp_server.BUNDLE_ENV_VAR, str(empty_bundle))

    payload = mcp_server.okf_search("anything")

    assert payload["index_state"] == "missing" and "cabal.okf" in payload["hint"]


def test_get_returns_full_body_for_known_id(bundle: Path) -> None:
    payload = mcp_server.okf_get(["skill:orchestrate"])

    assert payload["concepts"][0]["body"].strip()


def test_get_reports_unknown_ids_as_missing(bundle: Path) -> None:
    payload = mcp_server.okf_get(["concept:does-not-exist"])

    assert payload["missing"] == ["concept:does-not-exist"]


def test_context_pack_echoes_budget_and_returns_matches(bundle: Path) -> None:
    pack = mcp_server.okf_context_pack("pytest")

    assert pack["budget"] == "focused" and pack["matches"]


def test_context_pack_rejects_unknown_budget_with_hint(bundle: Path) -> None:
    payload = mcp_server.okf_context_pack("pytest", budget="gigantic")

    assert "error" in payload and "tiny" in payload["hint"]


def test_status_reports_fresh_index_with_counts(bundle: Path) -> None:
    payload = mcp_server.okf_status()

    assert payload["index_state"] == "fresh" and payload["concepts_count"] > 0


def test_status_reports_stale_after_bundle_document_changes(bundle: Path) -> None:
    doc = bundle / "skills" / "orchestrate.md"
    doc.write_text(doc.read_text(encoding="utf-8") + "\nEdited after indexing.\n", encoding="utf-8")

    payload = mcp_server.okf_status()

    assert payload["index_state"] == "stale"


def test_rrf_fusion_ranks_hit_shared_by_both_strategies_first() -> None:
    row = lambda concept_id: {  # noqa: E731
        "id": concept_id,
        "type": "skill",
        "title": concept_id,
        "resource": f"{concept_id}.md",
        "snippet": "",
    }
    fts_ranking = [row("only-fts"), row("shared")]
    semantic_ranking = [row("shared"), row("only-semantic")]

    fused = mcp_server._fuse_rrf([fts_ranking, semantic_ranking], limit=3)

    assert fused[0]["id"] == "shared"
