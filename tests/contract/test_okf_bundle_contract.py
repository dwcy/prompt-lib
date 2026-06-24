from __future__ import annotations

import json
from pathlib import Path

from cabal.okf.exporter import export_okf
from cabal.okf.frontmatter import extract_frontmatter, parse_frontmatter


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
FIXED_TIME = "2026-06-18T00:00:00Z"


def test_okf_bundle_contract_required_files_and_frontmatter(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    export_okf(FIXTURE_REPO, out, generated_at=FIXED_TIME)

    for required in ("index.md", "log.md", "manifest.json", "graph.json"):
        assert (out / required).exists()

    doc = out / "agents" / "python-architect.md"
    frontmatter, _ = extract_frontmatter(doc.read_text(encoding="utf-8"))
    parsed = parse_frontmatter(frontmatter)

    for key in ("type", "title", "description", "resource", "tags", "timestamp", "id"):
        assert parsed[key]
    assert parsed["resource"] == "global/agents/python-architect.md"
    assert "prompt-lib" in parsed["tags"]


def test_okf_bundle_contract_manifest_shape(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    export_okf(FIXTURE_REPO, out, generated_at=FIXED_TIME)

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["bundle_id"] == "prompt-lib"
    assert manifest["okf_version"] == "0.1"
    assert manifest["generated_at"] == FIXED_TIME
    assert "skills/orchestrate.md" in manifest["generated_files"]
    assert manifest["skipped"] == []
