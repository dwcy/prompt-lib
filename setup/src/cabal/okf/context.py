"""Graph-backed OKF context pack construction."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from cabal.okf.index import connect, search_index
from cabal.okf.usage import append_usage


BUDGETS: dict[str, dict[str, int]] = {
    "tiny": {"matches": 3, "neighbors": 3, "preview_chars": 360},
    "focused": {"matches": 6, "neighbors": 8, "preview_chars": 720},
    "full": {"matches": 12, "neighbors": 20, "preview_chars": 1600},
}


def _json_list(value: str) -> list[Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _fetch_concepts(conn, concept_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not concept_ids:
        return {}
    placeholders = ",".join("?" for _ in concept_ids)
    rows = conn.execute(
        f"""
        SELECT id, type, title, description, resource, doc, tags_json, body
        FROM concepts
        WHERE id IN ({placeholders})
        """,
        concept_ids,
    ).fetchall()
    return {row["id"]: dict(row) for row in rows}


def _concept_payload(row: dict[str, Any], *, preview_chars: int) -> dict[str, Any]:
    body = str(row.get("body") or "").strip()
    return {
        "id": row.get("id"),
        "type": row.get("type"),
        "title": row.get("title"),
        "description": row.get("description"),
        "resource": row.get("resource"),
        "doc": row.get("doc"),
        "tags": _json_list(str(row.get("tags_json") or "[]")),
        "body_preview": body[:preview_chars],
    }


def _edge_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "source": row.get("source"),
        "target": row.get("target"),
        "target_ref": row.get("target_ref"),
        "kind": row.get("kind"),
        "confidence": row.get("confidence"),
        "reason": row.get("reason"),
        "evidence": _json_list(str(row.get("evidence_json") or "[]")),
    }


def _estimate_tokens(payload: dict[str, Any]) -> int:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return max(1, round(len(text) / 4))


def build_context_pack(
    db_path: Path,
    query: str,
    *,
    budget: str = "focused",
    client: str = "cabal",
    entrypoint: str = "cli",
    usage_path: Path | None = None,
    record_usage: bool = True,
) -> dict[str, Any]:
    if budget not in BUDGETS:
        raise ValueError(f"Unknown context budget: {budget}")
    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"OKF index does not exist: {db}")

    started = time.perf_counter()
    limits = BUDGETS[budget]
    search_rows = search_index(db, query, limit=limits["matches"])
    match_ids = [str(row["id"]) for row in search_rows]
    why = [f"FTS search returned {len(match_ids)} direct matches."]

    with connect(db) as conn:
        concepts = _fetch_concepts(conn, match_ids)
        matches: list[dict[str, Any]] = []
        for row in search_rows:
            concept = concepts.get(str(row["id"]))
            if not concept:
                continue
            payload = _concept_payload(concept, preview_chars=limits["preview_chars"])
            payload["snippet"] = row.get("snippet")
            payload["rank"] = row.get("rank")
            matches.append(payload)

        evidence_edges: list[dict[str, Any]] = []
        expanded_ids: list[str] = []
        if match_ids:
            placeholders = ",".join("?" for _ in match_ids)
            edge_rows = conn.execute(
                f"""
                SELECT id, source, target, target_ref, kind, confidence, reason, evidence_json
                FROM edges
                WHERE source IN ({placeholders}) OR target IN ({placeholders})
                ORDER BY CASE WHEN kind = 'routes_to' THEN 0 ELSE 1 END, id
                LIMIT ?
                """,
                [*match_ids, *match_ids, limits["neighbors"] * 2],
            ).fetchall()
            for edge_row in edge_rows:
                edge = _edge_payload(dict(edge_row))
                evidence_edges.append(edge)
                for candidate in (edge.get("source"), edge.get("target")):
                    if candidate and candidate not in match_ids and candidate not in expanded_ids:
                        expanded_ids.append(str(candidate))
                    if len(expanded_ids) >= limits["neighbors"]:
                        break
                if len(expanded_ids) >= limits["neighbors"]:
                    break

        neighbor_rows = _fetch_concepts(conn, expanded_ids)
        expanded_concepts = [
            _concept_payload(neighbor_rows[concept_id], preview_chars=max(180, limits["preview_chars"] // 2))
            for concept_id in expanded_ids
            if concept_id in neighbor_rows
        ]

    if expanded_concepts:
        why.append(f"Graph expansion added {len(expanded_concepts)} related concepts.")
    else:
        why.append("Graph expansion found no additional indexed neighbors.")
    if evidence_edges:
        why.append(f"Included {len(evidence_edges)} graph evidence edges.")

    pack = {
        "query": query,
        "budget": budget,
        "matches": matches,
        "expanded_concepts": expanded_concepts,
        "evidence_edges": evidence_edges,
        "estimated_tokens": 0,
        "why": why,
    }
    pack["estimated_tokens"] = _estimate_tokens(pack)

    if record_usage:
        append_usage(
            action="okf_context_pack",
            query=query,
            budget=budget,
            client=client,
            entrypoint=entrypoint,
            included_concepts=[
                str(item["id"]) for item in [*matches, *expanded_concepts] if item.get("id")
            ],
            evidence_edge_count=len(evidence_edges),
            estimated_tokens=int(pack["estimated_tokens"]),
            duration_ms=round((time.perf_counter() - started) * 1000),
            usage_path=usage_path,
        )
    return pack


def render_context_human(pack: dict[str, Any]) -> str:
    lines = [
        f"OKF context pack: {pack['query']}",
        f"budget: {pack['budget']} ({pack['estimated_tokens']} estimated tokens)",
        "",
        "Matches",
    ]
    for item in pack.get("matches", []):
        lines.append(f"- {item['id']} :: {item.get('title') or item.get('resource')}")
        if item.get("snippet"):
            lines.append(f"  {item['snippet']}")
    if not pack.get("matches"):
        lines.append("- none")
    lines.append("")
    lines.append("Expanded concepts")
    for item in pack.get("expanded_concepts", []):
        lines.append(f"- {item['id']} :: {item.get('title') or item.get('resource')}")
    if not pack.get("expanded_concepts"):
        lines.append("- none")
    lines.append("")
    lines.append("Why")
    for reason in pack.get("why", []):
        lines.append(f"- {reason}")
    return "\n".join(lines) + "\n"
