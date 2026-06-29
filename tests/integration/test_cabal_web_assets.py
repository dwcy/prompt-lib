"""Static integration checks for the Cabal web asset bundle."""

from __future__ import annotations

from pathlib import Path


ASSET_ROOT = Path(__file__).resolve().parents[2] / "setup" / "src" / "cabal" / "web" / "assets"


def _read(name: str) -> str:
    return (ASSET_ROOT / name).read_text(encoding="utf-8")


def test_overview_markup_contains_metrics_status_and_retry_targets() -> None:
    html = _read("index.html")

    assert 'id="overview-metrics"' in html
    assert 'id="overview-terminal"' in html
    assert 'id="overview-sections"' in html
    assert 'id="refresh-current"' in html
    assert 'id="schema-badge"' in html
    assert 'src="/brand/cabal-logo.png"' in html


def test_sidebar_groups_match_terminal_setup_sections() -> None:
    html = _read("index.html")

    assert (
        html.index("Dev setup")
        < html.index("Repo setup")
        < html.index("Infrastructure setup")
        < html.index("Agent setup")
    )
    assert 'data-view-target="infrastructure"' in html
    assert 'data-view-target="github"' in html
    assert 'data-view-target="agent"' in html
    assert 'id="infrastructure-sections"' in html
    assert 'id="github-sections"' in html
    assert 'id="agent-summary"' in html


def test_tools_view_contains_search_filters_empty_state_and_detail_hooks() -> None:
    html = _read("index.html")
    js = _read("app.js")

    for marker in ("tool-search", "tool-category", "tool-status", "tool-channel", "tool-detail"):
        assert marker in html
    assert "No tools match the current filters" in js
    assert "data-tool-key" in js


def test_knowledge_and_project_views_have_filter_and_section_hooks() -> None:
    html = _read("index.html")
    js = _read("app.js")

    for marker in (
        "knowledge-search",
        "knowledge-type",
        "knowledge-relation",
        "knowledge-detail",
        "project-sections",
        "infrastructure-sections",
        "github-sections",
    ):
        assert marker in html
    assert "No graph bundle exists" in js
    assert "renderInfrastructure" in js
    assert "renderGithub" in js
    assert "git" in js and "github" in js and "supabase" in js and "vercel" in js


def test_css_has_no_external_fonts_or_orb_blob_decorations() -> None:
    css = _read("styles.css").lower()

    assert "@import" not in css
    assert "fonts.googleapis" not in css
    assert "orb" not in css
    assert "blob" not in css
    assert "radial-gradient" not in css


def test_css_defines_responsive_breakpoints_and_required_states() -> None:
    css = _read("styles.css")

    assert "@media (max-width: 1100px)" in css
    assert "@media (max-width: 720px)" in css
    for state in (
        "installed",
        "missing",
        "update_available",
        "unsupported",
        "manual_required",
        "source_unavailable",
        "loading",
        "error",
        "not_authed",
        "token_missing",
        "not_linked",
        "timeout",
    ):
        assert f'data-state="{state}"' in css


def test_frontend_copy_handler_redacts_selected_text() -> None:
    js = _read("app.js")

    assert 'document.addEventListener("copy"' in js
    assert "clipboardData.setData" in js
    assert "redact(text)" in js


def test_assets_do_not_embed_real_looking_fixture_secret() -> None:
    secret = "Bearer " + ("a" * 28)
    combined = "\n".join(_read(name) for name in ("index.html", "styles.css", "app.js"))

    assert secret not in combined
