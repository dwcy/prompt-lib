"""Read-only stdio MCP server exposing OKF search, concept retrieval, context packs, and status."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from cabal.okf.analytics import analyze_bundle
from cabal.okf.context import build_context_pack
from cabal.okf.index import (
    bundle_fingerprint,
    connect,
    default_index_path,
    fts_available,
)
from cabal.okf.prepare import ensure_fresh_index
from cabal.okf.preflight import run_preflight
from cabal.okf.search import search_index_logged
from cabal.okf.semantic import SemanticUnavailableError, semantic_available, semantic_search
from cabal.okf.usage import append_usage, read_usage

BUNDLE_ENV_VAR = "OKF_BUNDLE_ROOT"
RRF_K = 60
REBUILD_HINT = "Call the okf_prepare tool to rebuild (CLI equivalent: `python -m cabal.okf export --out docs/okf/prompt-lib` then `python -m cabal.okf index docs/okf/prompt-lib`)."

mcp = FastMCP("okf-rag")


def resolve_bundle_root() -> Path:
    env_value = os.environ.get(BUNDLE_ENV_VAR)
    if env_value:
        return Path(env_value)
    source_checkout = Path(__file__).resolve().parents[4] / "docs" / "okf" / "prompt-lib"
    if source_checkout.exists():
        return source_checkout
    return Path.cwd() / "docs" / "okf" / "prompt-lib"


def _repo_root(bundle_root: Path) -> Path | None:
    root = bundle_root.resolve()
    if root.parent.name == "okf" and root.parent.parent.name == "docs":
        return root.parents[2]
    return None


def _usage_path(bundle_root: Path) -> Path:
    repo = _repo_root(bundle_root)
    if repo is not None:
        return repo / ".cabal" / "okf" / "usage.jsonl"
    return bundle_root.resolve() / "usage.jsonl"


def index_freshness(bundle_root: Path, db_path: Path) -> str:
    """Return "fresh", "stale", or "missing" by comparing the stored bundle fingerprint."""
    if not db_path.exists():
        return "missing"
    try:
        with connect(db_path) as conn:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'bundle_fingerprint'"
            ).fetchone()
        stored = str(row["value"]) if row else ""
        return "fresh" if stored and stored == bundle_fingerprint(bundle_root) else "stale"
    except Exception:
        return "stale"


def _fuse_rrf(rankings: list[list[dict[str, Any]]], *, limit: int) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion over per-strategy rankings — position-only, so BM25 and cosine scores never need normalizing."""
    scores: dict[str, float] = {}
    rows: dict[str, dict[str, Any]] = {}
    for ranking in rankings:
        for position, row in enumerate(ranking):
            key = str(row["id"])
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + position + 1)
            rows.setdefault(key, row)
    ordered = sorted(scores, key=lambda key: scores[key], reverse=True)[:limit]
    return [
        {
            "id": rows[key]["id"],
            "type": rows[key]["type"],
            "title": rows[key]["title"],
            "resource": rows[key]["resource"],
            "snippet": rows[key].get("snippet", ""),
            "rrf_score": round(scores[key], 5),
        }
        for key in ordered
    ]


def _missing_index_payload(db_path: Path) -> dict[str, Any]:
    return {
        "error": f"OKF index not found at {db_path}.",
        "index_state": "missing",
        "hint": REBUILD_HINT,
    }


def _staleness_fields(bundle_root: Path, db_path: Path) -> dict[str, Any]:
    state = index_freshness(bundle_root, db_path)
    fields: dict[str, Any] = {"index_state": state}
    if state != "fresh":
        fields["warning"] = f"The OKF index is {state} — source files changed after the last export. {REBUILD_HINT}"
    return fields


@mcp.tool()
def okf_search(query: str, limit: int = 8, types: list[str] | None = None) -> dict[str, Any]:
    """Search the prompt-lib agent-ecosystem knowledge catalog (agents, skills, hooks, rules,
    templates, output styles, Spec Kit files). Prefer this over grep whenever the question is
    about how the ecosystem connects — which skills route to which agents, where
    responsibilities overlap, which concepts exist, are unused, or are related. Do NOT use it
    for arbitrary repository files: only exported OKF concept documents are indexed. Results
    are compact (id, type, title, snippet) — pass the ids of the 1-2 hits that matter to
    okf_get for full bodies instead of expanding on titles alone. `types` filters by concept
    type, e.g. ["skill", "agent"]. Heed any staleness warning in the response."""
    bundle_root = resolve_bundle_root()
    db_path = default_index_path(bundle_root)
    if not db_path.exists():
        return _missing_index_payload(db_path)
    usage_path = _usage_path(bundle_root)

    fts_rows = search_index_logged(
        db_path,
        query,
        client="claude",
        entrypoint="mcp",
        limit=limit,
        types=tuple(types or ()),
        usage_path=usage_path,
    )
    rankings = [fts_rows]
    semantic_state = "unavailable"
    if not types:
        try:
            semantic_rows = semantic_search(
                db_path,
                query,
                limit=limit,
                client="claude",
                entrypoint="mcp",
                usage_path=usage_path,
            )
            rankings.append(semantic_rows)
            semantic_state = "used"
        except SemanticUnavailableError:
            semantic_state = "unavailable"
        except Exception as exc:
            semantic_state = f"error: {exc}"
    else:
        semantic_state = "skipped: type filter is FTS-only"

    payload: dict[str, Any] = {
        "results": _fuse_rrf(rankings, limit=limit),
        "semantic": semantic_state,
    }
    payload.update(_staleness_fields(bundle_root, db_path))
    return payload


@mcp.tool()
def okf_get(ids: list[str]) -> dict[str, Any]:
    """Fetch the full concept documents for OKF ids returned by okf_search or okf_context_pack.
    This is the expensive tier — call it for the 1-2 ids that actually matter, not for every
    search hit. Returns each concept's description, tags, source resource path, and full body."""
    bundle_root = resolve_bundle_root()
    db_path = default_index_path(bundle_root)
    if not db_path.exists():
        return _missing_index_payload(db_path)

    started = time.perf_counter()
    placeholders = ",".join("?" for _ in ids)
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT id, type, title, description, resource, doc, tags_json, body
            FROM concepts
            WHERE id IN ({placeholders})
            """,
            list(ids),
        ).fetchall()
    found = {str(row["id"]): dict(row) for row in rows}
    concepts = [found[concept_id] for concept_id in ids if concept_id in found]
    missing = [concept_id for concept_id in ids if concept_id not in found]

    append_usage(
        action="okf_get",
        query=" ".join(ids),
        client="claude",
        entrypoint="mcp",
        included_concepts=list(found),
        estimated_tokens=round(sum(len(item["body"]) for item in concepts) / 4),
        duration_ms=round((time.perf_counter() - started) * 1000),
        usage_path=_usage_path(bundle_root),
    )

    payload: dict[str, Any] = {"concepts": concepts, "missing": missing}
    payload.update(_staleness_fields(bundle_root, db_path))
    return payload


@mcp.tool()
def okf_context_pack(query: str, budget: str = "focused") -> dict[str, Any]:
    """Build a token-budgeted, graph-expanded context pack for a task touching the prompt-lib
    agent ecosystem. Use this instead of several okf_search calls when starting non-trivial
    work: it returns direct matches with body previews, graph-related neighbor concepts, and
    the routing edges connecting them. `budget` is "tiny", "focused" (default), or "full" —
    the response reports its own estimated token cost so you can judge the spend."""
    bundle_root = resolve_bundle_root()
    db_path = default_index_path(bundle_root)
    if not db_path.exists():
        return _missing_index_payload(db_path)
    try:
        pack = build_context_pack(
            db_path,
            query,
            budget=budget,
            client="claude",
            entrypoint="mcp",
            usage_path=_usage_path(bundle_root),
        )
    except ValueError as exc:
        return {"error": str(exc), "hint": 'Valid budgets: "tiny", "focused", "full".'}
    pack.update(_staleness_fields(bundle_root, db_path))
    return pack


@mcp.tool()
def okf_preflight(task: str) -> dict[str, Any]:
    """Estimate the OKF scope of a task before pulling context: returns a small card with a
    scope size (S/M/L/XL), risk flags, likely-relevant concept ids, and a recommended context
    budget ("tiny", "focused", "full") to pass to okf_context_pack. Cheap — call it first for
    non-trivial tasks touching the prompt-lib agent ecosystem, then fetch only what it
    recommends. Never returns full bodies."""
    bundle_root = resolve_bundle_root()
    db_path = default_index_path(bundle_root)
    return run_preflight(
        db_path,
        task,
        client="claude",
        entrypoint="mcp",
        usage_path=_usage_path(bundle_root),
    )


@mcp.tool()
def okf_prepare(force: bool = False) -> dict[str, Any]:
    """Export the OKF bundle if missing and rebuild the SQLite index when its content
    fingerprint no longer matches the bundle. Idempotent — safe to call when okf_status or a
    staleness warning reports "stale" or "missing"; it only touches generated files
    (docs/okf/... bundle and index.sqlite), never source. Set force=true to rebuild anyway."""
    bundle_root = resolve_bundle_root()
    db_path = default_index_path(bundle_root)
    started = time.perf_counter()
    result_db, message, rebuilt = ensure_fresh_index(
        bundle_root,
        db_path,
        repo_root=_repo_root(bundle_root),
        force=force,
    )
    append_usage(
        action="okf_prepare",
        query=f"force={force}",
        client="claude",
        entrypoint="mcp",
        duration_ms=round((time.perf_counter() - started) * 1000),
        usage_path=_usage_path(bundle_root),
    )
    return {"db_path": str(result_db), "message": message, "rebuilt": rebuilt}


@mcp.tool()
def okf_analytics() -> dict[str, Any]:
    """Analyze the OKF bundle and graph for ecosystem health: agents receiving many routes,
    skills with wide fan-out, concepts never referenced, and skill overlap. Use for questions
    like "which agents are unused" or "where do skills overlap" — not for finding a specific
    concept (use okf_search for that)."""
    bundle_root = resolve_bundle_root()
    db_path = default_index_path(bundle_root)
    if not db_path.exists():
        return _missing_index_payload(db_path)
    started = time.perf_counter()
    report = analyze_bundle(bundle_root, db_path=db_path)
    append_usage(
        action="okf_analytics",
        query="bundle analytics",
        client="claude",
        entrypoint="mcp",
        estimated_tokens=round(len(str(report)) / 4),
        duration_ms=round((time.perf_counter() - started) * 1000),
        usage_path=_usage_path(bundle_root),
    )
    return report


@mcp.tool()
def okf_usage(limit: int = 20) -> dict[str, Any]:
    """Read the most recent OKF usage-ledger entries (queries, budgets, included concepts,
    token estimates) — the retrieval telemetry for this repo. Use it to answer "what has been
    looked up lately" or to check whether OKF retrieval is actually being used."""
    bundle_root = resolve_bundle_root()
    entries = read_usage(_usage_path(bundle_root), limit=limit)
    return {"entries": entries, "usage_path": str(_usage_path(bundle_root))}


@mcp.tool()
def okf_status() -> dict[str, Any]:
    """Report the OKF index's health: where the bundle and index live, whether full-text and
    semantic search are available, concept/chunk/edge counts, and whether the index is fresh
    or stale relative to the exported bundle. Call this first when another okf tool returns
    an error or a staleness warning."""
    bundle_root = resolve_bundle_root()
    db_path = default_index_path(bundle_root)
    payload: dict[str, Any] = {
        "bundle_root": str(bundle_root),
        "bundle_exists": bundle_root.exists(),
        "db_path": str(db_path),
        "index_state": index_freshness(bundle_root, db_path),
        "semantic_available": semantic_available(),
        "hint": REBUILD_HINT,
    }
    if db_path.exists():
        payload["fts_available"] = fts_available(db_path)
        with connect(db_path) as conn:
            for table in ("concepts", "chunks", "edges"):
                payload[f"{table}_count"] = conn.execute(
                    f"SELECT COUNT(*) AS n FROM {table}"
                ).fetchone()["n"]
    return payload


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
