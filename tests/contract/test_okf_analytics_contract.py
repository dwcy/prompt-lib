from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from cabal.okf.exporter import export_okf
from cabal.okf.index import build_index


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
FIXED_TIME = "2026-06-18T00:00:00Z"


def test_analytics_cli_contract_shape(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    db = tmp_path / "okf.sqlite"
    export_okf(FIXTURE_REPO, bundle, generated_at=FIXED_TIME)
    build_index(bundle, db)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cabal.okf",
            "analytics",
            str(bundle),
            "--db",
            str(db),
            "--format",
            "json",
            "--incoming-threshold",
            "1",
            "--fanout-threshold",
            "2",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    for key in (
        "agents_with_many_routes",
        "skills_with_many_routes",
        "agents_never_referenced",
        "skill_graph_overlap",
        "skill_text_overlap",
        "relation_density_by_category",
        "changed_concepts",
    ):
        assert key in payload


def test_index_cli_builds_sqlite_file(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    db = tmp_path / "okf.sqlite"
    export_okf(FIXTURE_REPO, bundle, generated_at=FIXED_TIME)

    subprocess.run(
        [sys.executable, "-m", "cabal.okf", "index", str(bundle), "--db", str(db)],
        check=True,
        text=True,
        capture_output=True,
    )

    assert db.exists()
