from __future__ import annotations

import json
from pathlib import Path

from cabal.okf.exporter import export_okf


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
FIXED_TIME = "2026-06-18T00:00:00Z"


def test_exporter_writes_manifest_and_is_deterministic(tmp_path: Path) -> None:
    out = tmp_path / "bundle"

    first = export_okf(FIXTURE_REPO, out, generated_at=FIXED_TIME)
    first_manifest = (out / "manifest.json").read_text(encoding="utf-8")
    second = export_okf(FIXTURE_REPO, out, generated_at=FIXED_TIME)
    second_manifest = (out / "manifest.json").read_text(encoding="utf-8")

    manifest = json.loads(first_manifest)
    assert first_manifest == second_manifest
    assert first.document_count == second.document_count
    assert manifest["source_categories"]["agent"] == 3
    assert "agents/python-architect.md" in manifest["generated_files"]


def test_exporter_omits_secret_like_source_text(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    skill = repo / "global" / "skills"
    skill.mkdir(parents=True)
    (skill / "secret.md").write_text(
        "# secret\n\nOPENAI_API_KEY=sk-" + ("a" * 28),
        encoding="utf-8",
    )
    out = tmp_path / "out"

    export_okf(repo, out, generated_at=FIXED_TIME)

    assert "OPENAI_API_KEY" not in (out / "skills" / "secret.md").read_text(
        encoding="utf-8"
    )
