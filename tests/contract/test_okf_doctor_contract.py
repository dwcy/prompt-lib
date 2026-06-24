from __future__ import annotations

import json
from pathlib import Path

from cabal.okf.doctor import doctor_bundle, render_human, render_json
from cabal.okf.exporter import export_okf


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"
MALFORMED = Path(__file__).resolve().parents[1] / "fixtures" / "okf_bundle_malformed"
FIXED_TIME = "2026-06-18T00:00:00Z"


def test_okf_doctor_contract_json_output(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    export_okf(FIXTURE_REPO, out, generated_at=FIXED_TIME)

    payload = json.loads(render_json(doctor_bundle(out, FIXTURE_REPO)))

    assert payload["ok"] is True
    assert payload["summary"]["errors"] == 0
    assert "documents" in payload["summary"]
    assert all(finding["severity"] != "error" for finding in payload["findings"])


def test_okf_doctor_contract_human_output_for_failure() -> None:
    report = doctor_bundle(MALFORMED, FIXTURE_REPO)
    text = render_human(report)

    assert report.exit_code == 1
    assert "OKF doctor failed" in text
    assert "OKF003" in text
