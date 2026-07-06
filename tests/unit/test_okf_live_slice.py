from __future__ import annotations

from pathlib import Path

from cabal.okf.context import build_context_pack
from cabal.okf.exporter import export_okf
from cabal.okf.index import build_index
from cabal.okf.preflight import run_preflight
from cabal.okf.usage import read_usage


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
FIXED_TIME = "2026-06-18T00:00:00Z"


def _indexed_bundle(tmp_path: Path) -> tuple[Path, Path]:
    bundle = tmp_path / "bundle"
    db = tmp_path / "okf.sqlite"
    export_okf(FIXTURE_REPO, bundle, generated_at=FIXED_TIME)
    build_index(bundle, db)
    return bundle, db


def test_context_pack_records_visible_usage(tmp_path: Path) -> None:
    _, db = _indexed_bundle(tmp_path)
    ledger = tmp_path / "usage.jsonl"

    pack = build_context_pack(
        db,
        "orchestrate python tester",
        budget="tiny",
        usage_path=ledger,
    )

    assert pack["budget"] == "tiny"
    assert pack["estimated_tokens"] > 0
    assert pack["matches"]
    entries = read_usage(ledger)
    assert entries[-1]["action"] == "okf_context_pack"
    assert entries[-1]["included_concepts"]


def test_preflight_reports_scope_and_records_usage(tmp_path: Path) -> None:
    _, db = _indexed_bundle(tmp_path)
    ledger = tmp_path / "usage.jsonl"

    report = run_preflight(
        db,
        "Add an MCP-backed OKF context pack for Claude and Cursor",
        usage_path=ledger,
    )

    assert report["scope"] in {"S", "M", "L", "XL"}
    assert "mcp_protocol" in report["risk_flags"]
    assert report["recommended_budget"] in {"tiny", "focused", "full"}
    entries = read_usage(ledger)
    assert entries[-1]["action"] == "okf_preflight"
    assert entries[-1]["entrypoint"] == "cli"
