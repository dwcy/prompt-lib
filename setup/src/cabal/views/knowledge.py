"""Cabal Knowledge screen for OKF graph status."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Select, Static

from cabal.app_widgets import AppHeader
from cabal.knowledge_rag_logic import (
    DEFAULT_RAG_QUERY,
    bundle_root,
    format_context_summary,
    format_preflight_summary,
    format_result_list,
    index_path,
    prepare_index,
    rag_status_text,
    resolve_budget,
    resolve_query,
    resolve_repo_root,
    usage_path,
    usage_summary_text,
)
from cabal.okf.context import build_context_pack
from cabal.okf.doctor import doctor_bundle, render_human
from cabal.okf.exporter import export_okf
from cabal.okf.preflight import run_preflight
from cabal.okf.recommendations import recommend_from_graph
from cabal.okf.search import search_index_logged
from cabal.okf.semantic import SemanticUnavailableError, semantic_available, semantic_search
from cabal.okf.viewer import generate_viewer


class KnowledgeScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("e", "export", "Export"),
        Binding("d", "doctor", "Doctor"),
        Binding("v", "view_graph", "Graph"),
        Binding("i", "rebuild_index", "Rebuild Index"),
        Binding("p", "preflight", "Preflight"),
        Binding("s", "search_index", "Search"),
        Binding("n", "semantic_search", "Semantic"),
        Binding("c", "context_pack", "Context"),
        Binding("u", "refresh_usage", "Usage"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]OKF Knowledge Graph[/bold bright_magenta]",
                classes="panel",
            )
            yield Static(
                "[bold]Export behavior[/bold]\n"
                "Export writes the OKF bundle to `docs/okf/prompt-lib/`, including "
                "`graph.json` for machine-readable relations. Claude, Codex, and "
                "other AI tools can use it when prompts, repo instructions, or "
                "future analytics/RAG flows point them there; exporting does not "
                "auto-inject the bundle into every session.",
                id="okf-export-help",
                classes="panel",
            )
            yield Static(self._status_text(), id="okf-status", classes="panel")
            with Horizontal(id="okf-actions"):
                yield Button("[E] Export", id="okf-export", variant="primary")
                yield Button("[D] Doctor", id="okf-doctor", variant="primary")
                yield Button("[V] Graph", id="okf-viewer", variant="primary")
                yield Button("Back (Esc)", id="okf-back")
            yield Static("", id="okf-recommendations", classes="panel")
            yield Static(self._rag_status(), id="okf-rag-status", classes="panel")
            yield Input(
                value=DEFAULT_RAG_QUERY,
                placeholder="Task or context query",
                id="okf-rag-query",
            )
            with Horizontal(id="okf-rag-actions"):
                yield Button("[I] Rebuild Index", id="okf-index", variant="primary")
                yield Button("[P] Preflight", id="okf-preflight", variant="primary")
                yield Button("[S] Search", id="okf-search", variant="primary")
                yield Button("[N] Semantic", id="okf-semantic", variant="primary")
            with Horizontal(id="okf-rag-context-actions"):
                yield Select(
                    [("Tiny", "tiny"), ("Focused", "focused"), ("Full", "full")],
                    value="focused",
                    id="okf-budget",
                    prompt="Budget",
                )
                yield Button("[C] Context", id="okf-context", variant="success")
                yield Button("[U] Usage", id="okf-usage-refresh")
            yield Static("", id="okf-rag-output", classes="panel")
            yield Static(self._usage_summary(), id="okf-usage", classes="panel")
        yield Footer(show_command_palette=False)

    def _repo_root(self) -> Path:
        try:
            project_path = self.app.project_path()
        except Exception:
            project_path = None
        return resolve_repo_root(project_path)

    def _status_text(self) -> str:
        graph = bundle_root(self._repo_root()) / "graph.json"
        if graph.exists():
            recs = recommend_from_graph(graph, "Python service architecture")
            first = recs[0]["target"] if recs else "no route recommendation"
            return (
                f"[green]OKF graph present.[/green]\nRecommendation sample: `{first}`"
            )
        return "[yellow]No OKF graph generated yet.[/yellow]"

    def _rag_status(self) -> str:
        repo = self._repo_root()
        return rag_status_text(bundle_root(repo), index_path(repo), usage_path(repo))

    def _usage_summary(self) -> str:
        return usage_summary_text(usage_path(self._repo_root()))

    def _query_input_value(self) -> str:
        try:
            return self.query_one("#okf-rag-query", Input).value
        except Exception:
            return ""

    def _budget_select_value(self) -> object:
        try:
            return self.query_one("#okf-budget", Select).value
        except Exception:
            return "focused"

    def _refresh_rag_panel(self) -> None:
        self.query_one("#okf-rag-status", Static).update(self._rag_status())
        self.query_one("#okf-usage", Static).update(self._usage_summary())

    def action_export(self) -> None:
        repo = self._repo_root()
        result = export_okf(repo, bundle_root(repo))
        self.query_one("#okf-status", Static).update(
            "[green]"
            f"Exported {result.document_count} documents and "
            f"{result.relation_count} relations to `{result.bundle_root}`.\n"
            "[/green]"
            "`graph.json` is ready for prompts, project instructions, and "
            "future OKF analytics/RAG indexing."
        )
        self._refresh_rag_panel()

    def action_doctor(self) -> None:
        repo = self._repo_root()
        report = doctor_bundle(bundle_root(repo), repo)
        self.query_one("#okf-status", Static).update(render_human(report))

    def action_view_graph(self) -> None:
        graph_path = bundle_root(self._repo_root()) / "graph.json"
        status = self.query_one("#okf-status", Static)
        if not graph_path.exists():
            status.update(
                "[yellow]No OKF graph to view yet — run [E] Export first to "
                "generate the bundle.[/yellow]"
            )
            return
        try:
            html_path = generate_viewer(graph_path, graph_path.parent / "graph.html")
            webbrowser.open(html_path.as_uri())
        except Exception as exc:
            status.update(f"[red]Could not open graph viewer: {exc}[/red]")
            return
        status.update(
            f"[green]Opened graph viewer in your browser: `{html_path}`.[/green]"
        )

    def action_rebuild_index(self) -> None:
        output = self.query_one("#okf-rag-output", Static)
        repo = self._repo_root()
        try:
            _, message, _ = prepare_index(repo, bundle_root(repo), index_path(repo), force=True)
        except Exception as exc:
            output.update(f"[red]Could not rebuild OKF index: {escape_markup(str(exc))}[/red]")
            return
        output.update(f"[green]{message}[/green]")
        self._refresh_rag_panel()

    def action_preflight(self) -> None:
        output = self.query_one("#okf-rag-output", Static)
        repo = self._repo_root()
        try:
            db, _, _ = prepare_index(repo, bundle_root(repo), index_path(repo), force=False)
            report = run_preflight(
                db,
                resolve_query(self._query_input_value()),
                client="cabal",
                entrypoint="ui",
                usage_path=usage_path(repo),
            )
        except Exception as exc:
            output.update(f"[red]Preflight failed: {escape_markup(str(exc))}[/red]")
            return
        output.update(format_preflight_summary(report))
        self._refresh_rag_panel()

    def action_context_pack(self) -> None:
        output = self.query_one("#okf-rag-output", Static)
        repo = self._repo_root()
        try:
            db, _, _ = prepare_index(repo, bundle_root(repo), index_path(repo), force=False)
            pack = build_context_pack(
                db,
                resolve_query(self._query_input_value()),
                budget=resolve_budget(self._budget_select_value()),
                client="cabal",
                entrypoint="ui",
                usage_path=usage_path(repo),
            )
        except Exception as exc:
            output.update(f"[red]Context pack failed: {escape_markup(str(exc))}[/red]")
            return
        output.update(format_context_summary(pack))
        self._refresh_rag_panel()

    def action_search_index(self) -> None:
        output = self.query_one("#okf-rag-output", Static)
        repo = self._repo_root()
        try:
            db, _, _ = prepare_index(repo, bundle_root(repo), index_path(repo), force=False)
            results = search_index_logged(
                db,
                resolve_query(self._query_input_value()),
                client="cabal",
                entrypoint="ui",
                usage_path=usage_path(repo),
            )
        except Exception as exc:
            output.update(f"[red]Search failed: {escape_markup(str(exc))}[/red]")
            return
        output.update(format_result_list(results, heading="Search Results"))
        self._refresh_rag_panel()

    def action_semantic_search(self) -> None:
        output = self.query_one("#okf-rag-output", Static)
        if not semantic_available():
            output.update(
                "[yellow]Semantic search is unavailable — install the optional "
                "embedding dependency (`uv sync --extra semantic`), or use "
                "Search (S) instead.[/yellow]"
            )
            return
        repo = self._repo_root()
        try:
            db, _, _ = prepare_index(repo, bundle_root(repo), index_path(repo), force=False)
            results = semantic_search(
                db,
                resolve_query(self._query_input_value()),
                client="cabal",
                entrypoint="ui",
                usage_path=usage_path(repo),
            )
        except SemanticUnavailableError:
            output.update(
                "[yellow]Semantic search is unavailable — install the optional "
                "embedding dependency (`uv sync --extra semantic`), or use "
                "Search (S) instead.[/yellow]"
            )
            return
        except Exception as exc:
            output.update(f"[red]Semantic search failed: {escape_markup(str(exc))}[/red]")
            return
        output.update(format_result_list(results, heading="Semantic Results"))
        self._refresh_rag_panel()

    def action_refresh_usage(self) -> None:
        self._refresh_rag_panel()
        self.query_one("#okf-rag-output", Static).update("[green]Usage refreshed.[/green]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "okf-export":
            self.action_export()
        elif bid == "okf-doctor":
            self.action_doctor()
        elif bid == "okf-viewer":
            self.action_view_graph()
        elif bid == "okf-index":
            self.action_rebuild_index()
        elif bid == "okf-preflight":
            self.action_preflight()
        elif bid == "okf-search":
            self.action_search_index()
        elif bid == "okf-semantic":
            self.action_semantic_search()
        elif bid == "okf-context":
            self.action_context_pack()
        elif bid == "okf-usage-refresh":
            self.action_refresh_usage()
        elif bid == "okf-back":
            self.app.pop_screen()
