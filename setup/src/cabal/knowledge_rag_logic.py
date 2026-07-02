# -*- coding: utf-8 -*-
"""Pure path resolution + rendering logic for the Cabal Knowledge screen's OKF RAG panel.

No Textual here — plain functions taking explicit path/dict arguments, mirroring
mcp_view_logic.py's split between view (compose/events) and worker (logic).
"""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape as escape_markup

from cabal.okf.prepare import ensure_fresh_index
from cabal.okf.semantic import semantic_available
from cabal.okf.usage import read_usage


DEFAULT_RAG_QUERY = "009 okf analytics rag context pack usage ledger preflight"


def bundle_root(repo_root: Path) -> Path:
    return repo_root / "docs" / "okf" / "prompt-lib"


def cache_root(repo_root: Path) -> Path:
    return repo_root / ".cabal" / "okf"


def index_path(repo_root: Path) -> Path:
    return cache_root(repo_root) / "index.sqlite"


def usage_path(repo_root: Path) -> Path:
    return cache_root(repo_root) / "usage.jsonl"


def resolve_repo_root(project_path: Path | None) -> Path:
    return project_path if project_path is not None else Path.cwd()


def resolve_query(raw_value: str) -> str:
    return raw_value.strip() or DEFAULT_RAG_QUERY


def resolve_budget(raw_value: object) -> str:
    return str(raw_value) if raw_value in {"tiny", "focused", "full"} else "focused"


def prepare_index(
    repo_root: Path, bundle_root: Path, db_path: Path, *, force: bool = False
) -> tuple[Path, str, bool]:
    """Thin wrapper around ensure_fresh_index binding the repo_root export fallback."""
    return ensure_fresh_index(bundle_root, db_path, repo_root=repo_root, force=force)


def rag_status_text(bundle_root: Path, index_path: Path, usage_path: Path) -> str:
    graph = bundle_root / "graph.json"
    entries = read_usage(usage_path, limit=0)
    graph_state = "[green]ready[/green]" if graph.exists() else "[yellow]missing[/yellow]"
    index_state = "[green]ready[/green]" if index_path.exists() else "[yellow]missing[/yellow]"
    semantic_state = (
        "[green]available[/green]"
        if semantic_available()
        else "[yellow]unavailable (install `uv sync --extra semantic`)[/yellow]"
    )
    return (
        "[bold bright_magenta]OKF RAG[/bold bright_magenta]\n"
        f"Bundle: {graph_state} `{escape_markup(str(bundle_root))}`\n"
        f"Index: {index_state} `{escape_markup(str(index_path))}`\n"
        f"Usage: {len(entries)} entries `{escape_markup(str(usage_path))}`\n"
        f"Semantic: {semantic_state}\n"
        "[dim]MCP adapter is not registered yet; this panel exercises the shared service layer.[/dim]"
    )


def usage_summary_text(usage_path: Path, *, limit: int = 5) -> str:
    entries = read_usage(usage_path, limit=limit)
    if not entries:
        return "[bold]Recent OKF usage[/bold]\n[dim]No usage entries yet.[/dim]"
    lines = ["[bold]Recent OKF usage[/bold]"]
    for entry in entries:
        concepts = ", ".join(entry.get("included_concepts") or [])
        if len(concepts) > 96:
            concepts = concepts[:93] + "..."
        lines.append(
            "- {timestamp} {entrypoint}/{action} {budget} {tokens} tokens: {query}".format(
                timestamp=escape_markup(str(entry.get("timestamp", "?"))),
                entrypoint=escape_markup(str(entry.get("entrypoint", "?"))),
                action=escape_markup(str(entry.get("action", "?"))),
                budget=escape_markup(str(entry.get("budget", "none"))),
                tokens=escape_markup(str(entry.get("estimated_tokens", 0))),
                query=escape_markup(str(entry.get("query_preview", ""))),
            )
        )
        if concepts:
            lines.append(f"  [dim]{escape_markup(concepts)}[/dim]")
    return "\n".join(lines)


def format_preflight_summary(report: dict) -> str:
    risks = ", ".join(report.get("risk_flags") or []) or "none"
    likely = ", ".join(report.get("likely_areas") or []) or "none"
    lines = [
        "[bold]Preflight[/bold]",
        f"scope: {escape_markup(str(report.get('scope', '?')))}",
        f"budget: {escape_markup(str(report.get('recommended_budget', '?')))}",
        f"index: {escape_markup(str(report.get('index_state', '?')))}",
        f"risk: {escape_markup(risks)}",
        f"likely: {escape_markup(likely)}",
        "",
        "Why",
    ]
    for reason in report.get("why", []):
        lines.append(f"- {escape_markup(str(reason))}")
    return "\n".join(lines)


def format_context_summary(pack: dict) -> str:
    lines = [
        "[bold]Context Pack[/bold]",
        f"budget: {escape_markup(str(pack.get('budget', '?')))}",
        f"estimated tokens: {escape_markup(str(pack.get('estimated_tokens', 0)))}",
        "",
        "Matches",
    ]
    for item in pack.get("matches", [])[:8]:
        lines.append(
            "- {concept} :: {resource}".format(
                concept=escape_markup(str(item.get("id", "?"))),
                resource=escape_markup(str(item.get("resource", ""))),
            )
        )
    if not pack.get("matches"):
        lines.append("- none")
    expanded = pack.get("expanded_concepts") or []
    if expanded:
        lines.append("")
        lines.append("Expanded")
        for item in expanded[:6]:
            lines.append(f"- {escape_markup(str(item.get('id', '?')))}")
    lines.append("")
    lines.append("Why")
    for reason in pack.get("why", []):
        lines.append(f"- {escape_markup(str(reason))}")
    return "\n".join(lines)


def format_result_list(results: list[dict], *, heading: str) -> str:
    lines = [f"[bold]{escape_markup(heading)}[/bold]"]
    if not results:
        lines.append("[dim]No results.[/dim]")
        return "\n".join(lines)
    for item in results:
        score_suffix = f" ({round(item['score'], 2)})" if "score" in item else ""
        lines.append(
            "- {id} [{type}] {title} :: {resource}{score}".format(
                id=escape_markup(str(item.get("id", "?"))),
                type=escape_markup(str(item.get("type", "?"))),
                title=escape_markup(str(item.get("title", ""))),
                resource=escape_markup(str(item.get("resource", ""))),
                score=escape_markup(score_suffix),
            )
        )
        snippet = item.get("snippet")
        if snippet:
            text = str(snippet)
            if len(text) > 160:
                text = text[:157] + "..."
            lines.append(f"  [dim]{escape_markup(text)}[/dim]")
    return "\n".join(lines)
