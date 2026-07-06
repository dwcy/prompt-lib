"""Append-only usage ledger for OKF retrieval calls."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cabal.okf.paths import has_secret_value


VALID_CLIENTS = {"cabal", "claude", "cursor", "unknown"}
VALID_ENTRYPOINTS = {"cli", "preflight", "mcp", "ui"}
VALID_BUDGETS = {"tiny", "focused", "full", "none"}


def default_usage_path(repo_root: Path | None = None) -> Path:
    return Path(repo_root or Path.cwd()) / ".cabal" / "okf" / "usage.jsonl"


def _hash_query(query: str) -> str:
    return "sha256:" + hashlib.sha256(query.encode("utf-8")).hexdigest()


def _preview(query: str, *, limit: int = 160) -> str:
    compact = re.sub(r"\s+", " ", query).strip()
    if has_secret_value(compact):
        return "[redacted secret-like query]"
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def append_usage(
    *,
    action: str,
    query: str,
    budget: str = "none",
    client: str = "cabal",
    entrypoint: str = "cli",
    included_concepts: list[str] | None = None,
    evidence_edge_count: int = 0,
    estimated_tokens: int = 0,
    cache_state: str = "fresh",
    duration_ms: int = 0,
    usage_path: Path | None = None,
) -> dict[str, Any]:
    if client not in VALID_CLIENTS:
        client = "unknown"
    if entrypoint not in VALID_ENTRYPOINTS:
        entrypoint = "cli"
    if budget not in VALID_BUDGETS:
        budget = "none"
    entry = {
        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "client": client,
        "entrypoint": entrypoint,
        "action": action,
        "query_hash": _hash_query(query),
        "query_preview": _preview(query),
        "budget": budget,
        "included_concepts": list(included_concepts or []),
        "evidence_edge_count": int(evidence_edge_count),
        "estimated_tokens": int(estimated_tokens),
        "cache_state": cache_state,
        "duration_ms": int(duration_ms),
    }
    path = Path(usage_path or default_usage_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def read_usage(usage_path: Path | None = None, *, limit: int = 20) -> list[dict[str, Any]]:
    path = Path(usage_path or default_usage_path())
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    if limit <= 0:
        return entries
    return entries[-limit:]


def render_usage_human(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "No OKF usage entries found.\n"
    lines = ["OKF usage ledger"]
    for entry in entries:
        concepts = ", ".join(entry.get("included_concepts") or [])
        if len(concepts) > 120:
            concepts = concepts[:117] + "..."
        lines.append(
            "- {timestamp} {entrypoint}/{action} {budget} {estimated_tokens} tokens: {query}".format(
                timestamp=entry.get("timestamp", "?"),
                entrypoint=entry.get("entrypoint", "?"),
                action=entry.get("action", "?"),
                budget=entry.get("budget", "none"),
                estimated_tokens=entry.get("estimated_tokens", 0),
                query=entry.get("query_preview", ""),
            )
        )
        if concepts:
            lines.append(f"  concepts: {concepts}")
    return "\n".join(lines) + "\n"
