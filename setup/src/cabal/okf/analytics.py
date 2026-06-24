"""Analytics and overlap detection for OKF catalogs."""

from __future__ import annotations

import itertools
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from cabal.okf.index import build_index, connect, default_index_path


def _tokens(text: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "into",
        "source",
        "category",
        "prompt",
        "lib",
    }
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2 and token not in stop}


def _ensure_index(bundle_root: Path, db_path: Path | None) -> Path:
    db = Path(db_path or default_index_path(bundle_root))
    if not db.exists():
        build_index(bundle_root, db)
    return db


def _rows(conn, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params)]


def _changed_concepts(conn, previous_db_path: Path | None) -> list[str]:
    if not previous_db_path:
        return []
    previous_db_path = Path(previous_db_path)
    if not previous_db_path.exists():
        return []
    current = {
        row["id"]: row["body_hash"]
        for row in conn.execute("SELECT id, body_hash FROM concepts")
    }
    with connect(previous_db_path) as previous:
        old = {
            row["id"]: row["body_hash"]
            for row in previous.execute("SELECT id, body_hash FROM concepts")
        }
    return sorted(concept_id for concept_id, body_hash in current.items() if old.get(concept_id) != body_hash)


def _graph_overlap(conn, threshold: int) -> list[dict[str, Any]]:
    skill_targets: dict[str, set[str]] = defaultdict(set)
    for row in conn.execute(
        """
        SELECT source, target
        FROM edges
        WHERE kind = 'routes_to' AND source LIKE 'skill:%' AND target IS NOT NULL
        """
    ):
        skill_targets[row["source"]].add(row["target"])
    overlaps: list[dict[str, Any]] = []
    for left, right in itertools.combinations(sorted(skill_targets), 2):
        shared = sorted(skill_targets[left] & skill_targets[right])
        if len(shared) >= threshold:
            overlaps.append({"skills": [left, right], "shared_agents": shared, "score": len(shared)})
    return sorted(overlaps, key=lambda item: (-item["score"], item["skills"]))[:25]


def _text_overlap(conn, limit: int = 25) -> list[dict[str, Any]]:
    skills = _rows(
        conn,
        """
        SELECT id, title, body, tags_json
        FROM concepts
        WHERE type = 'skill'
        ORDER BY id
        """,
    )
    vectors = {
        row["id"]: _tokens(" ".join([row["title"], row["body"], row["tags_json"]]))
        for row in skills
    }
    overlaps: list[dict[str, Any]] = []
    for left, right in itertools.combinations(sorted(vectors), 2):
        a = vectors[left]
        b = vectors[right]
        if not a or not b:
            continue
        shared = sorted(a & b)
        score = len(shared) / math.sqrt(len(a) * len(b))
        if score >= 0.08 and shared:
            overlaps.append(
                {
                    "skills": [left, right],
                    "score": round(score, 3),
                    "shared_terms": shared[:12],
                }
            )
    return sorted(overlaps, key=lambda item: (-item["score"], item["skills"]))[:limit]


def analyze_bundle(
    bundle_root: Path,
    *,
    db_path: Path | None = None,
    previous_db_path: Path | None = None,
    incoming_threshold: int = 4,
    fanout_threshold: int = 6,
    overlap_threshold: int = 2,
) -> dict[str, Any]:
    bundle_root = Path(bundle_root)
    db = _ensure_index(bundle_root, db_path)
    with connect(db) as conn:
        agents_with_many_routes = _rows(
            conn,
            """
            SELECT target AS agent, COUNT(*) AS incoming_routes
            FROM edges
            WHERE kind = 'routes_to' AND target LIKE 'agent:%'
            GROUP BY target
            HAVING COUNT(*) >= ?
            ORDER BY incoming_routes DESC, agent
            """,
            (incoming_threshold,),
        )
        skills_with_many_routes = _rows(
            conn,
            """
            SELECT source AS skill, COUNT(*) AS outgoing_routes
            FROM edges
            WHERE kind = 'routes_to' AND source LIKE 'skill:%'
            GROUP BY source
            HAVING COUNT(*) >= ?
            ORDER BY outgoing_routes DESC, skill
            """,
            (fanout_threshold,),
        )
        agents_never_referenced = _rows(
            conn,
            """
            SELECT c.id AS agent, c.title, c.resource
            FROM concepts c
            LEFT JOIN edges e ON e.target = c.id AND e.kind = 'routes_to'
            WHERE c.type = 'agent'
            GROUP BY c.id
            HAVING COUNT(e.id) = 0
            ORDER BY c.id
            """,
        )
        relation_density = _rows(
            conn,
            """
            SELECT c.type AS category,
                   COUNT(DISTINCT c.id) AS concepts,
                   COUNT(e.id) AS outgoing_relations,
                   ROUND(CAST(COUNT(e.id) AS REAL) / MAX(COUNT(DISTINCT c.id), 1), 3) AS outgoing_per_concept
            FROM concepts c
            LEFT JOIN edges e ON e.source = c.id
            GROUP BY c.type
            ORDER BY outgoing_per_concept DESC, category
            """,
        )
        same_agent_reason = _rows(
            conn,
            """
            SELECT target AS agent, reason, COUNT(*) AS route_count, GROUP_CONCAT(source, ',') AS skills
            FROM edges
            WHERE kind = 'routes_to' AND target IS NOT NULL
            GROUP BY target, reason
            HAVING COUNT(*) > 1
            ORDER BY route_count DESC, agent
            """,
        )
        return {
            "bundle_root": str(bundle_root),
            "db_path": str(db),
            "agents_with_many_routes": agents_with_many_routes,
            "skills_with_many_routes": skills_with_many_routes,
            "agents_never_referenced": agents_never_referenced,
            "skill_graph_overlap": _graph_overlap(conn, overlap_threshold),
            "skill_text_overlap": _text_overlap(conn),
            "skills_same_agent_similar_reasons": [
                {
                    "agent": row["agent"],
                    "reason": row["reason"],
                    "route_count": row["route_count"],
                    "skills": sorted(row["skills"].split(",")),
                }
                for row in same_agent_reason
            ],
            "relation_density_by_category": relation_density,
            "changed_concepts": _changed_concepts(conn, previous_db_path),
        }


def render_analytics_human(report: dict[str, Any]) -> str:
    lines = ["OKF analytics", f"bundle: {report['bundle_root']}", f"index: {report['db_path']}", ""]
    sections = (
        ("Agents with many incoming routes", "agents_with_many_routes", "agent", "incoming_routes"),
        ("Skills with many outgoing routes", "skills_with_many_routes", "skill", "outgoing_routes"),
        ("Agents never referenced", "agents_never_referenced", "agent", None),
        ("Relation density by category", "relation_density_by_category", "category", "outgoing_per_concept"),
    )
    for title, key, name_key, value_key in sections:
        lines.append(title)
        rows = report.get(key, [])
        if not rows:
            lines.append("- none")
        for row in rows[:10]:
            suffix = f" ({row[value_key]})" if value_key else ""
            lines.append(f"- {row[name_key]}{suffix}")
        lines.append("")
    lines.append("Skill graph overlap")
    for item in report.get("skill_graph_overlap", [])[:10]:
        lines.append(f"- {', '.join(item['skills'])}: {', '.join(item['shared_agents'])}")
    if not report.get("skill_graph_overlap"):
        lines.append("- none")
    lines.append("")
    lines.append("Skill text overlap")
    for item in report.get("skill_text_overlap", [])[:10]:
        lines.append(f"- {', '.join(item['skills'])}: {', '.join(item['shared_terms'])}")
    if not report.get("skill_text_overlap"):
        lines.append("- none")
    lines.append("")
    changed = report.get("changed_concepts", [])
    lines.append(f"Changed concepts since previous index: {len(changed)}")
    for concept_id in changed[:10]:
        lines.append(f"- {concept_id}")
    return "\n".join(lines) + "\n"
