"""Contract tests for the okf-rag MCP server against specs/009 okf-rag-mcp.contract.md."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from cabal.okf import mcp_server
from cabal.okf.exporter import export_okf
from cabal.okf.index import build_index
from cabal.okf.semantic import SemanticUnavailableError
from cabal.okf.usage import read_usage

FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
FIXED_TIME = "2026-06-18T00:00:00Z"
REQUIRED_TOOLS = {
    "okf_prepare",
    "okf_search",
    "okf_preflight",
    "okf_context_pack",
    "okf_analytics",
    "okf_usage",
}


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


def test_server_exposes_every_contract_required_tool():
    tools = asyncio.run(mcp_server.mcp.list_tools())

    assert REQUIRED_TOOLS.issubset({tool.name for tool in tools})


def test_context_pack_tool_returns_contract_shape(bundle: Path) -> None:
    pack = mcp_server.okf_context_pack("pytest")

    assert {
        "query",
        "budget",
        "matches",
        "expanded_concepts",
        "evidence_edges",
        "estimated_tokens",
        "why",
    } <= set(pack)


def test_preflight_tool_returns_contract_shape(bundle: Path) -> None:
    report = mcp_server.okf_preflight("add a pytest suite for the orchestrate skill")

    assert {
        "task",
        "scope",
        "risk_flags",
        "likely_areas",
        "recommended_budget",
        "index_state",
        "why",
    } <= set(report)


def test_preflight_scope_and_budget_use_contract_vocabulary(bundle: Path) -> None:
    report = mcp_server.okf_preflight("add a pytest suite")

    assert report["scope"] in {"S", "M", "L", "XL"} and report["recommended_budget"] in {
        "tiny",
        "focused",
        "full",
    }


def test_usage_tool_returns_ledger_entries_with_mcp_entrypoint(bundle: Path) -> None:
    mcp_server.okf_search("pytest")

    payload = mcp_server.okf_usage()

    assert payload["entries"] and all(entry["entrypoint"] == "mcp" for entry in payload["entries"])


def test_tool_calls_append_usage_ledger_entries(bundle: Path) -> None:
    mcp_server.okf_analytics()

    entries = read_usage(bundle / "usage.jsonl", limit=0)

    assert any(entry["action"] == "okf_analytics" for entry in entries)


def test_missing_index_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_bundle = tmp_path / "empty"
    empty_bundle.mkdir()
    monkeypatch.setenv(mcp_server.BUNDLE_ENV_VAR, str(empty_bundle))

    payload = mcp_server.okf_search("anything")

    assert payload["index_state"] == "missing"


def test_prepare_reports_up_to_date_index_without_rebuilding(bundle: Path) -> None:
    result = mcp_server.okf_prepare()

    assert result["rebuilt"] is False


def test_prepare_rebuilds_index_after_bundle_document_changes(bundle: Path) -> None:
    doc = bundle / "skills" / "orchestrate.md"
    doc.write_text(doc.read_text(encoding="utf-8") + "\nEdited after indexing.\n", encoding="utf-8")

    result = mcp_server.okf_prepare()

    assert result["rebuilt"] is True


def test_tool_results_serialize_to_json(bundle: Path) -> None:
    payload = mcp_server.okf_status()

    assert json.loads(json.dumps(payload)) == payload
