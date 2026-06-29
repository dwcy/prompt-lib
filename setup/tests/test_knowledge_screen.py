# -*- coding: utf-8 -*-
"""Smoke tests for KnowledgeScreen OKF actions, including the graph viewer."""

from __future__ import annotations

import pytest
from textual.widgets import Button

from cabal.app import CabalApp
from cabal.views import knowledge
from cabal.views.knowledge import KnowledgeScreen


@pytest.mark.asyncio
async def test_viewer_button_present():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = KnowledgeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#okf-viewer", Button)


@pytest.mark.asyncio
async def test_pressing_viewer_generates_and_opens_html(tmp_path, monkeypatch):
    bundle = tmp_path / "docs" / "okf" / "prompt-lib"
    bundle.mkdir(parents=True)
    graph_json = bundle / "graph.json"
    graph_json.write_text("{}", encoding="utf-8")
    html_path = bundle / "graph.html"
    html_path.write_text("<html></html>", encoding="utf-8")

    generated: list[tuple] = []
    opened: list[str] = []
    monkeypatch.setattr(
        knowledge,
        "generate_viewer",
        lambda graph, out: generated.append((graph, out)) or html_path,
    )
    monkeypatch.setattr(
        knowledge.webbrowser, "open", lambda uri: opened.append(uri) or True
    )

    app = CabalApp()
    async with app.run_test() as pilot:
        app.selected_project = tmp_path
        screen = KnowledgeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen.on_button_pressed(
            Button.Pressed(screen.query_one("#okf-viewer", Button))
        )

    assert generated == [(graph_json, html_path)]
    assert opened == [html_path.as_uri()]


@pytest.mark.asyncio
async def test_pressing_viewer_without_bundle_reports_export_first(
    tmp_path, monkeypatch
):
    called: list[object] = []
    monkeypatch.setattr(
        knowledge, "generate_viewer", lambda *a, **k: called.append(a) or tmp_path
    )

    app = CabalApp()
    async with app.run_test() as pilot:
        app.selected_project = tmp_path
        screen = KnowledgeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen.on_button_pressed(
            Button.Pressed(screen.query_one("#okf-viewer", Button))
        )

        status = screen.query_one("#okf-status").render()

    assert called == []
    assert "Export first" in str(status)
