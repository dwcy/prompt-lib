"""Cabal Knowledge screen for OKF graph status."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from cabal.app_widgets import AppHeader
from cabal.okf.doctor import doctor_bundle, render_human
from cabal.okf.exporter import export_okf
from cabal.okf.recommendations import recommend_from_graph


class KnowledgeScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("e", "export", "Export"),
        Binding("d", "doctor", "Doctor"),
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
                yield Button("Back (Esc)", id="okf-back")
            yield Static("", id="okf-recommendations", classes="panel")
        yield Footer(show_command_palette=False)

    def _repo_root(self) -> Path:
        try:
            return self.app.project_path()
        except Exception:
            return Path.cwd()

    def _bundle_root(self) -> Path:
        return self._repo_root() / "docs" / "okf" / "prompt-lib"

    def _status_text(self) -> str:
        graph = self._bundle_root() / "graph.json"
        if graph.exists():
            recs = recommend_from_graph(graph, "Python service architecture")
            first = recs[0]["target"] if recs else "no route recommendation"
            return f"[green]OKF graph present.[/green]\nRecommendation sample: `{first}`"
        return "[yellow]No OKF graph generated yet.[/yellow]"

    def action_export(self) -> None:
        result = export_okf(self._repo_root(), self._bundle_root())
        self.query_one("#okf-status", Static).update(
            "[green]"
            f"Exported {result.document_count} documents and "
            f"{result.relation_count} relations to `{result.bundle_root}`.\n"
            "[/green]"
            "`graph.json` is ready for prompts, project instructions, and "
            "future OKF analytics/RAG indexing."
        )

    def action_doctor(self) -> None:
        report = doctor_bundle(self._bundle_root(), self._repo_root())
        self.query_one("#okf-status", Static).update(render_human(report))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "okf-export":
            self.action_export()
        elif bid == "okf-doctor":
            self.action_doctor()
        elif bid == "okf-back":
            self.app.pop_screen()
