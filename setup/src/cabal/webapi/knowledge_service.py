# -*- coding: utf-8 -*-
"""Knowledge graph/read-side payloads for the web API.

The OKF exporters and RAG helpers already live in cabal.okf; this module only
normalizes those shared service outputs into stable web payloads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cabal.knowledge_rag_logic import (
    DEFAULT_RAG_QUERY,
    bundle_root,
    index_path,
    resolve_budget,
    resolve_query,
    resolve_repo_root,
    usage_path,
)
from cabal.okf.context import build_context_pack
from cabal.okf.preflight import run_preflight
from cabal.okf.search import search_index_logged
from cabal.okf.semantic import semantic_available, semantic_search
from cabal.okf.usage import read_usage
from cabal.webapi.envelope import compute_precondition_digest


def _repo_root(project: Path | None) -> Path:
    return resolve_repo_root(Path(project) if project is not None else None)


def _paths(project: Path | None) -> dict[str, Path]:
    repo = _repo_root(project)
    return {
        "repo_root": repo,
        "bundle_root": bundle_root(repo),
        "index_path": index_path(repo),
        "usage_path": usage_path(repo),
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _count_usage(path: Path) -> int:
    return len(read_usage(path, limit=0))


def knowledge_digest(project: Path | None) -> str:
    paths = _paths(project)
    graph_path = paths["bundle_root"] / "graph.json"
    manifest_path = paths["bundle_root"] / "manifest.json"
    index = paths["index_path"]
    payload = {
        "repo_root": str(paths["repo_root"]),
        "graph_mtime": graph_path.stat().st_mtime if graph_path.exists() else None,
        "manifest_mtime": manifest_path.stat().st_mtime if manifest_path.exists() else None,
        "index_mtime": index.stat().st_mtime if index.exists() else None,
    }
    return compute_precondition_digest(payload)


def knowledge_summary(project: Path | None) -> dict[str, Any]:
    paths = _paths(project)
    graph_path = paths["bundle_root"] / "graph.json"
    manifest_path = paths["bundle_root"] / "manifest.json"
    graph = _read_json(graph_path) or {}
    manifest = _read_json(manifest_path) or {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    counts = graph.get("counts") if isinstance(graph.get("counts"), dict) else {}
    return {
        "available": graph_path.exists(),
        "repo_root": str(paths["repo_root"]),
        "bundle_root": str(paths["bundle_root"]),
        "index_path": str(paths["index_path"]),
        "usage_path": str(paths["usage_path"]),
        "generated_at": graph.get("generated_at") or manifest.get("generated_at"),
        "index_available": paths["index_path"].exists(),
        "semantic_available": semantic_available(),
        "usage_count": _count_usage(paths["usage_path"]),
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "by_type": counts.get("nodes_by_type", {}),
            "by_relation": counts.get("edges_by_kind", {}),
            "findings_by_severity": counts.get("findings_by_severity", {}),
        },
        "digest": knowledge_digest(project),
    }


def _normalize_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(node.get("id") or ""),
        "type": str(node.get("type") or "unknown"),
        "label": str(node.get("label") or node.get("title") or node.get("id") or ""),
        "resource": str(node.get("resource") or ""),
        "doc": str(node.get("doc") or ""),
        "tags": [str(item) for item in node.get("tags") or []],
        "metrics": node.get("metrics") if isinstance(node.get("metrics"), dict) else {},
    }


def _normalize_edge(edge: dict[str, Any]) -> dict[str, Any]:
    target = edge.get("target") or edge.get("target_ref") or ""
    return {
        "id": str(edge.get("id") or f"{edge.get('source', '')}->{target}"),
        "from": str(edge.get("source") or ""),
        "to": str(target),
        "target_ref": str(edge.get("target_ref") or target),
        "relation": str(edge.get("kind") or "relates_to"),
        "confidence": str(edge.get("confidence") or ""),
        "reason": str(edge.get("reason") or ""),
        "evidence": edge.get("evidence") if isinstance(edge.get("evidence"), list) else [],
    }


def knowledge_graph(
    project: Path | None,
    *,
    limit: int = 500,
    cursor: str | None = None,
    q: str | None = None,
    node_type: str | None = None,
    relation: str | None = None,
) -> dict[str, Any]:
    paths = _paths(project)
    graph_path = paths["bundle_root"] / "graph.json"
    graph = _read_json(graph_path)
    if graph is None:
        summary = knowledge_summary(project)
        return {
            "available": False,
            "generated_at": None,
            "nodes": [],
            "edges": [],
            "counts": summary["counts"],
            "next_cursor": None,
            "total_nodes": 0,
            "total_edges": 0,
        }

    raw_nodes = [_normalize_node(node) for node in graph.get("nodes", []) if isinstance(node, dict)]
    raw_edges = [_normalize_edge(edge) for edge in graph.get("edges", []) if isinstance(edge, dict)]
    search = (q or "").strip().lower()
    if search:
        raw_nodes = [
            node
            for node in raw_nodes
            if search in node["id"].lower()
            or search in node["label"].lower()
            or search in node["resource"].lower()
            or any(search in tag.lower() for tag in node["tags"])
        ]
    if node_type:
        raw_nodes = [node for node in raw_nodes if node["type"] == node_type]

    start = 0
    if cursor:
        try:
            start = max(0, int(cursor))
        except ValueError:
            start = 0
    page_size = min(max(limit, 25), 2000)
    filtered_ids = {node["id"] for node in raw_nodes}
    page_nodes = raw_nodes[start : start + page_size]
    visible_ids = {node["id"] for node in page_nodes}
    page_edges = [
        edge
        for edge in raw_edges
        if edge["from"] in visible_ids
        and edge["to"] in filtered_ids
        and (relation is None or edge["relation"] == relation)
    ]
    filtered_edges = [
        edge
        for edge in raw_edges
        if edge["from"] in filtered_ids
        and edge["to"] in filtered_ids
        and (relation is None or edge["relation"] == relation)
    ]
    next_cursor = str(start + page_size) if start + page_size < len(raw_nodes) else None
    summary = knowledge_summary(project)
    return {
        "available": True,
        "generated_at": graph.get("generated_at"),
        "nodes": page_nodes,
        "edges": page_edges,
        "counts": summary["counts"],
        "next_cursor": next_cursor,
        "total_nodes": len(raw_nodes),
        "total_edges": len(filtered_edges),
    }


def knowledge_search(project: Path | None, *, query: str, mode: str = "fulltext", limit: int = 10) -> dict[str, Any]:
    paths = _paths(project)
    resolved_query = resolve_query(query)
    if not paths["index_path"].exists():
        return {
            "available": False,
            "mode": mode,
            "query": resolved_query,
            "status": "missing_index",
            "message": f"OKF index not found at {paths['index_path']}. Run Export or Rebuild index.",
            "results": [],
        }
    if mode == "semantic":
        if not semantic_available():
            return {
                "available": False,
                "mode": "semantic",
                "query": resolved_query,
                "status": "semantic_unavailable",
                "message": "Semantic search requires the optional semantic dependency.",
                "results": [],
            }
        results = semantic_search(
            paths["index_path"],
            resolved_query,
            limit=limit,
            client="cabal",
            entrypoint="ui",
            usage_path=paths["usage_path"],
            record_usage=False,
        )
    else:
        results = search_index_logged(
            paths["index_path"],
            resolved_query,
            client="cabal",
            entrypoint="ui",
            usage_path=paths["usage_path"],
            limit=limit,
            record_usage=False,
        )
        mode = "fulltext"
    return {
        "available": True,
        "mode": mode,
        "query": resolved_query,
        "status": "ok",
        "message": "",
        "results": results,
    }


def knowledge_context_pack(
    project: Path | None,
    *,
    query: str,
    budget: str = "focused",
) -> dict[str, Any]:
    paths = _paths(project)
    resolved_query = resolve_query(query)
    resolved_budget = resolve_budget(budget)
    if not paths["index_path"].exists():
        return {
            "available": False,
            "query": resolved_query,
            "budget": resolved_budget,
            "status": "missing_index",
            "message": f"OKF index not found at {paths['index_path']}.",
            "pack": None,
        }
    pack = build_context_pack(
        paths["index_path"],
        resolved_query,
        budget=resolved_budget,
        client="cabal",
        entrypoint="ui",
        usage_path=paths["usage_path"],
        record_usage=False,
    )
    return {
        "available": True,
        "query": resolved_query,
        "budget": resolved_budget,
        "status": "ok",
        "message": "",
        "pack": pack,
    }


def knowledge_preflight(project: Path | None, *, task: str) -> dict[str, Any]:
    paths = _paths(project)
    resolved_task = resolve_query(task or DEFAULT_RAG_QUERY)
    report = run_preflight(
        paths["index_path"],
        resolved_task,
        client="cabal",
        entrypoint="ui",
        usage_path=paths["usage_path"],
        record_usage=False,
    )
    return {"task": resolved_task, "report": report}


def knowledge_usage(project: Path | None, *, limit: int = 20) -> dict[str, Any]:
    paths = _paths(project)
    entries = read_usage(paths["usage_path"], limit=max(0, min(limit, 200)))
    return {"entries": entries, "usage_path": str(paths["usage_path"]), "total_entries": _count_usage(paths["usage_path"])}
