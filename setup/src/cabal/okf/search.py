"""Logged OKF FTS search: search_index() plus one usage-ledger entry per call."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from cabal.okf.index import search_index
from cabal.okf.usage import append_usage


def search_index_logged(
    db_path: Path,
    query: str,
    *,
    client: str,
    entrypoint: str,
    usage_path: Path | None = None,
    limit: int = 10,
    types: tuple[str, ...] = (),
    record_usage: bool = True,
) -> list[dict[str, Any]]:
    """Run search_index() and append one okf_search usage-ledger entry (unless record_usage=False)."""
    started = time.perf_counter()
    rows = search_index(db_path, query, limit=limit, types=types)
    if record_usage:
        append_usage(
            action="okf_search",
            query=query,
            budget="none",
            client=client,
            entrypoint=entrypoint,
            included_concepts=[str(row["id"]) for row in rows],
            estimated_tokens=round(len(json.dumps(rows, sort_keys=True)) / 4),
            duration_ms=round((time.perf_counter() - started) * 1000),
            usage_path=usage_path,
        )
    return rows
