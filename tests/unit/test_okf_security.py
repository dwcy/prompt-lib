from __future__ import annotations

from pathlib import Path

from cabal.okf.exporter import export_okf
from cabal.okf.paths import has_secret_value


def test_generated_output_does_not_contain_secret_fixture_value(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    agents = repo / "global" / "agents"
    agents.mkdir(parents=True)
    secret = "ghp_" + ("a" * 36)
    (agents / "secret-agent.md").write_text(
        f"# secret-agent\n\nToken: {secret}\n",
        encoding="utf-8",
    )

    out = tmp_path / "bundle"
    export_okf(repo, out, generated_at="2026-06-18T00:00:00Z")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in out.rglob("*") if path.is_file())

    assert has_secret_value(secret)
    assert secret not in combined
