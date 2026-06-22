from __future__ import annotations

from pathlib import Path

from cabal.okf.doctor import doctor_bundle
from cabal.okf.exporter import export_okf


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"


def test_export_then_doctor_integration(tmp_path: Path) -> None:
    out = tmp_path / "bundle"

    export_okf(FIXTURE_REPO, out, generated_at="2026-06-18T00:00:00Z")
    report = doctor_bundle(out, FIXTURE_REPO)

    assert report.ok
