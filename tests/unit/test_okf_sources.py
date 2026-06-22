from __future__ import annotations

from pathlib import Path

from cabal.okf.sources import discover_sources


FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "okf_repo"


def test_discover_sources_finds_configured_categories() -> None:
    sources = discover_sources(FIXTURE_REPO)
    categories = {source.category for source in sources}

    assert {"agent", "skill", "hook", "rule", "tool", "spec"}.issubset(categories)
    assert any(source.resource == "global/agents/python-architect.md" for source in sources)


def test_discover_sources_is_deterministic() -> None:
    first = [source.resource for source in discover_sources(FIXTURE_REPO)]
    second = [source.resource for source in discover_sources(FIXTURE_REPO)]

    assert first == second
