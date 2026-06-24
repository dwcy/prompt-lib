from __future__ import annotations

from pathlib import Path

from cabal.okf.doctor import doctor_bundle
from cabal.okf.exporter import export_okf


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
MALFORMED = Path(__file__).resolve().parents[1] / "fixtures" / "okf_bundle_malformed"
FIXED_TIME = "2026-06-18T00:00:00Z"


def test_doctor_passes_generated_bundle(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    export_okf(FIXTURE_REPO, out, generated_at=FIXED_TIME)

    report = doctor_bundle(out, FIXTURE_REPO)

    assert report.ok
    assert report.summary["errors"] == 0


def test_doctor_reports_malformed_bundle_findings() -> None:
    report = doctor_bundle(MALFORMED, FIXTURE_REPO)
    codes = {finding.code for finding in report.findings}

    assert not report.ok
    assert {"OKF003", "OKF005", "OKF101"}.issubset(codes)
