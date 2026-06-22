"""Graph-backed recommendation helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def recommend_from_graph(graph_path: Path, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    query_tokens = _tokens(query)
    recommendations: list[dict[str, Any]] = []
    for edge in graph.get("edges", []):
        if edge.get("kind") != "routes_to" or not edge.get("target"):
            continue
        target = nodes.get(edge["target"])
        if not target:
            continue
        haystack = " ".join(
            [
                edge.get("reason", ""),
                edge.get("source", ""),
                edge.get("target", ""),
                target.get("label", ""),
                target.get("resource", ""),
                " ".join(item.get("text", "") for item in edge.get("evidence", [])),
            ]
        )
        score = len(query_tokens & _tokens(haystack))
        if score == 0:
            continue
        recommendations.append(
            {
                "target": edge["target"],
                "score": score,
                "reason": edge.get("reason", ""),
                "source": edge.get("source"),
                "evidence": edge.get("evidence", []),
            }
        )
    return sorted(recommendations, key=lambda item: (-item["score"], item["target"]))[:limit]
