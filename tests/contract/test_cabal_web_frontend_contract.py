"""Static frontend contract tests for the Cabal web UI."""

from __future__ import annotations

import re
from pathlib import Path


ASSET_ROOT = Path(__file__).resolve().parents[2] / "setup" / "src" / "cabal" / "web" / "assets"


def _asset(name: str) -> str:
    return (ASSET_ROOT / name).read_text(encoding="utf-8")


def test_index_references_only_local_static_assets() -> None:
    html = _asset("index.html")

    assert 'href="/styles.css"' in html
    assert 'src="/app.js"' in html
    assert "https://" not in html
    assert "http://" not in html


def test_no_external_script_stylesheet_or_font_cdn_is_required() -> None:
    combined = "\n".join(_asset(name) for name in ("index.html", "styles.css", "app.js"))

    assert "@import" not in combined
    assert "fonts.googleapis" not in combined
    assert "cdn." not in combined
    assert re.search(r"<script[^>]+https?://", combined) is None
    assert re.search(r"<link[^>]+https?://", combined) is None


def test_required_view_containers_exist() -> None:
    html = _asset("index.html")

    for view_id in (
        "view-overview",
        "view-agent",
        "view-infrastructure",
        "view-github",
        "view-tools",
        "view-knowledge",
        "view-project",
        "view-diagnostics",
    ):
        assert f'id="{view_id}"' in html


def test_javascript_defines_required_api_endpoint_paths() -> None:
    js = _asset("app.js")

    for path in (
        "/api/health",
        "/api/overview",
        "/api/tools",
        "/api/knowledge",
        "/api/project-health",
        "/api/diagnostics",
    ):
        assert path in js


def test_static_assets_contain_required_state_labels() -> None:
    combined = _asset("index.html") + _asset("app.js")

    for text in (
        "Loading overview",
        "Loading agent setup",
        "Loading infrastructure overview",
        "Loading GitHub",
        "Loading tools",
        "Loading knowledge",
        "Loading project health",
        "Loading diagnostics",
        "Schema mismatch",
        "No graph bundle exists",
        "No tools match",
    ):
        assert text in combined


def test_frontend_assets_do_not_embed_raw_fixture_token() -> None:
    token = "sk-proj-" + ("x" * 32)
    combined = "\n".join(_asset(name) for name in ("index.html", "styles.css", "app.js"))

    assert token not in combined


def test_primary_controls_are_keyboard_focusable_and_labelled() -> None:
    html = _asset("index.html")

    assert "<main" in html
    assert 'aria-label="Primary"' in html
    assert 'aria-label="Overview"' in html
    assert "Dev setup" in html
    assert "Repo setup" in html
    assert "Infrastructure setup" in html
    assert "Agent setup" in html
    assert 'aria-label="Refresh current view"' in html
    assert 'type="button"' in html
    assert 'type="search"' in html
    assert "aria-label=\"Tool category\"" in html
