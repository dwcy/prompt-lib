# -*- coding: utf-8 -*-
"""Smoke tests for KnowledgeScreen OKF actions, including the graph viewer."""

from __future__ import annotations

import pytest
from textual.widgets import Button, Input, Select, Static

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
        assert screen.query_one("#okf-rag-query", Input)
        assert screen.query_one("#okf-budget", Select)
        assert screen.query_one("#okf-preflight", Button)
        assert screen.query_one("#okf-context", Button)
        assert screen.query_one("#okf-search", Button)
        assert screen.query_one("#okf-semantic", Button)
        assert screen.query_one("#okf-usage", Static)


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


@pytest.mark.asyncio
async def test_rag_preflight_button_updates_output_and_usage(tmp_path, monkeypatch):
    db = tmp_path / ".cabal" / "okf" / "index.sqlite"
    calls: list[tuple] = []

    monkeypatch.setattr(
        knowledge,
        "prepare_index",
        lambda *a, **k: (db, "Indexed test OKF catalog.", True),
    )

    def fake_preflight(db_path, task, *, client, entrypoint, usage_path):
        calls.append((db_path, task, client, entrypoint, usage_path))
        return {
            "task": task,
            "scope": "L",
            "risk_flags": ["mcp_protocol", "token_heavy"],
            "likely_areas": ["okf", "mcp"],
            "recommended_budget": "focused",
            "index_state": "fresh",
            "why": ["test preflight"],
        }

    monkeypatch.setattr(knowledge, "run_preflight", fake_preflight)
    monkeypatch.setattr(
        knowledge,
        "usage_summary_text",
        lambda path, limit=5: "[bold]Recent OKF usage[/bold]\n- okf_preflight test entry",
    )

    app = CabalApp()
    async with app.run_test() as pilot:
        app.selected_project = tmp_path
        screen = KnowledgeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen.query_one("#okf-rag-query", Input).value = "MCP RAG visible usage"
        screen.on_button_pressed(
            Button.Pressed(screen.query_one("#okf-preflight", Button))
        )

        output = str(screen.query_one("#okf-rag-output", Static).render())
        usage = str(screen.query_one("#okf-usage", Static).render())

    assert calls == [
        (
            db,
            "MCP RAG visible usage",
            "cabal",
            "ui",
            tmp_path / ".cabal" / "okf" / "usage.jsonl",
        )
    ]
    assert "scope: L" in output
    assert "mcp_protocol" in output
    assert "okf_preflight" in usage


@pytest.mark.asyncio
async def test_rag_context_button_uses_selected_budget(tmp_path, monkeypatch):
    db = tmp_path / ".cabal" / "okf" / "index.sqlite"
    calls: list[tuple] = []

    monkeypatch.setattr(
        knowledge,
        "prepare_index",
        lambda *a, **k: (db, "Indexed test OKF catalog.", True),
    )

    def fake_context(db_path, query, *, budget, client, entrypoint, usage_path):
        calls.append((db_path, query, budget, client, entrypoint, usage_path))
        return {
            "query": query,
            "budget": budget,
            "matches": [
                {
                    "id": "spec:009",
                    "resource": "specs/009-okf-analytics-rag/plan.md",
                }
            ],
            "expanded_concepts": [],
            "evidence_edges": [],
            "estimated_tokens": 123,
            "why": ["test context"],
        }

    monkeypatch.setattr(knowledge, "build_context_pack", fake_context)
    monkeypatch.setattr(knowledge, "usage_summary_text", lambda path, limit=5: "")

    app = CabalApp()
    async with app.run_test() as pilot:
        app.selected_project = tmp_path
        screen = KnowledgeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen.query_one("#okf-rag-query", Input).value = "009 context pack"
        screen.query_one("#okf-budget", Select).value = "tiny"
        screen.on_button_pressed(
            Button.Pressed(screen.query_one("#okf-context", Button))
        )

        output = str(screen.query_one("#okf-rag-output", Static).render())

    assert calls == [
        (
            db,
            "009 context pack",
            "tiny",
            "cabal",
            "ui",
            tmp_path / ".cabal" / "okf" / "usage.jsonl",
        )
    ]
    assert "estimated tokens: 123" in output
    assert "spec:009" in output


@pytest.mark.asyncio
async def test_rag_search_button_logs_ui_entrypoint_and_renders_results(
    tmp_path, monkeypatch
):
    db = tmp_path / ".cabal" / "okf" / "index.sqlite"
    calls: list[tuple] = []

    monkeypatch.setattr(
        knowledge,
        "prepare_index",
        lambda *a, **k: (db, "Indexed test OKF catalog.", True),
    )

    def fake_search(db_path, query, *, client, entrypoint, usage_path):
        calls.append((db_path, query, client, entrypoint, usage_path))
        return [
            {
                "id": "spec:009",
                "type": "spec",
                "title": "OKF analytics and RAG",
                "resource": "specs/009-okf-analytics-rag/plan.md",
            }
        ]

    monkeypatch.setattr(knowledge, "search_index_logged", fake_search)
    monkeypatch.setattr(knowledge, "usage_summary_text", lambda path, limit=5: "")

    app = CabalApp()
    async with app.run_test() as pilot:
        app.selected_project = tmp_path
        screen = KnowledgeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen.query_one("#okf-rag-query", Input).value = "keyword search test"
        screen.on_button_pressed(
            Button.Pressed(screen.query_one("#okf-search", Button))
        )

        output = str(screen.query_one("#okf-rag-output", Static).render())

    assert calls == [
        (
            db,
            "keyword search test",
            "cabal",
            "ui",
            tmp_path / ".cabal" / "okf" / "usage.jsonl",
        )
    ]
    assert "Search Results" in output
    assert "spec:009" in output


@pytest.mark.asyncio
async def test_rag_semantic_button_shows_unavailable_message_without_calling_search(
    tmp_path, monkeypatch
):
    calls: list[tuple] = []

    monkeypatch.setattr(knowledge, "semantic_available", lambda: False)
    monkeypatch.setattr(
        knowledge,
        "semantic_search",
        lambda *a, **k: calls.append((a, k)) or [],
    )

    app = CabalApp()
    async with app.run_test() as pilot:
        app.selected_project = tmp_path
        screen = KnowledgeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen.on_button_pressed(
            Button.Pressed(screen.query_one("#okf-semantic", Button))
        )

        output = str(screen.query_one("#okf-rag-output", Static).render())

    assert calls == []
    assert "unavailable" in output


@pytest.mark.asyncio
async def test_rag_semantic_button_renders_scored_results_when_available(
    tmp_path, monkeypatch
):
    db = tmp_path / ".cabal" / "okf" / "index.sqlite"
    calls: list[tuple] = []

    monkeypatch.setattr(knowledge, "semantic_available", lambda: True)
    monkeypatch.setattr(
        knowledge,
        "prepare_index",
        lambda *a, **k: (db, "Indexed test OKF catalog.", True),
    )

    def fake_semantic_search(db_path, query, *, client, entrypoint, usage_path):
        calls.append((db_path, query, client, entrypoint, usage_path))
        return [
            {
                "id": "spec:009",
                "type": "spec",
                "title": "OKF analytics and RAG",
                "resource": "specs/009-okf-analytics-rag/plan.md",
                "score": 0.8734,
            }
        ]

    monkeypatch.setattr(knowledge, "semantic_search", fake_semantic_search)
    monkeypatch.setattr(knowledge, "usage_summary_text", lambda path, limit=5: "")

    app = CabalApp()
    async with app.run_test() as pilot:
        app.selected_project = tmp_path
        screen = KnowledgeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen.query_one("#okf-rag-query", Input).value = "semantic search test"
        screen.on_button_pressed(
            Button.Pressed(screen.query_one("#okf-semantic", Button))
        )

        output = str(screen.query_one("#okf-rag-output", Static).render())

    assert calls == [
        (
            db,
            "semantic search test",
            "cabal",
            "ui",
            tmp_path / ".cabal" / "okf" / "usage.jsonl",
        )
    ]
    assert "Semantic Results" in output
    assert "spec:009" in output
    assert "0.87" in output
