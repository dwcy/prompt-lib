from cabal.news_feed import CURATED_SOURCES, normalize_json, normalize_xml


def test_curated_catalog_contains_required_source_groups():
    ids = {source.id for source in CURATED_SOURCES}
    assert {"openai", "anthropic", "nvidia", "deepseek", "hacker-news", "cisa-kev", "nvd", "azure-status"} <= ids


def test_xml_normalization_handles_atom_links():
    body = b"<feed xmlns='http://www.w3.org/2005/Atom'><entry><title>Release</title><link href='https://example.test/release'/><updated>2026-08-29T10:00:00Z</updated><summary>Details</summary></entry></feed>"
    items = normalize_xml(CURATED_SOURCES[0], body)
    assert len(items) == 1
    assert items[0].canonical_url == "https://example.test/release"


def test_json_advisory_normalization_preserves_security_metadata():
    source = next(source for source in CURATED_SOURCES if source.id == "cisa-kev")
    items = normalize_json(source, b'{"vulnerabilities":[{"cveID":"CVE-2026-0001","shortDescription":"Example"}]}')
    assert items[0].security["identifier"] == "CVE-2026-0001"
