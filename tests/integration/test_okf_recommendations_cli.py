from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from cabal.okf.exporter import export_okf


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"


def test_recommendation_cli_returns_match(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    export_okf(FIXTURE_REPO, out, generated_at="2026-06-18T00:00:00Z")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cabal.okf",
            "recommend",
            str(out / "graph.json"),
            "Python service architecture",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "agent:python-architect" in result.stdout
