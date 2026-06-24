from __future__ import annotations

from cabal.okf.frontmatter import dump_document, extract_frontmatter, parse_frontmatter


def test_dump_document_is_deterministic_and_parseable() -> None:
    metadata = {
        "type": "agent",
        "title": "python-architect",
        "description": "Designs Python services.",
        "resource": "global/agents/python-architect.md",
        "tags": ["prompt-lib", "agent"],
        "timestamp": "2026-06-18T00:00:00Z",
        "id": "agent:python-architect",
    }

    first = dump_document(metadata, "# python-architect\n")
    second = dump_document(metadata, "# python-architect\n")
    parsed = parse_frontmatter(extract_frontmatter(first)[0])

    assert first == second
    assert parsed["type"] == "agent"
    assert parsed["tags"] == ["prompt-lib", "agent"]


def test_extract_frontmatter_rejects_missing_block() -> None:
    metadata, body = extract_frontmatter("# no frontmatter")

    assert metadata == ""
    assert body == "# no frontmatter"
