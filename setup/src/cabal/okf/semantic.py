"""Local/offline semantic search over cached OKF chunk embeddings (optional fastembed dependency)."""

from __future__ import annotations

import array
import math
import time
from pathlib import Path
from typing import Any

from cabal.okf.index import connect
from cabal.okf.usage import append_usage


MODEL_NAME = "BAAI/bge-small-en-v1.5"


class SemanticUnavailableError(RuntimeError):
    """Raised when the optional fastembed dependency isn't installed."""


def semantic_available() -> bool:
    """Report whether the optional embedding dependency is importable."""
    try:
        import fastembed  # noqa: F401
    except ImportError:
        return False
    return True


_model = None


def _load_model():
    global _model
    if _model is None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise SemanticUnavailableError(
                "Semantic search requires the optional 'semantic' extra. Install with `uv sync --extra semantic`."
            ) from exc
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def _ensure_table(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chunk_embeddings (text_hash TEXT PRIMARY KEY, model TEXT NOT NULL, vector BLOB NOT NULL)"
    )


def _pack(vector) -> bytes:
    return array.array("f", vector).tobytes()


def _unpack(blob: bytes) -> array.array:
    vec = array.array("f")
    vec.frombytes(blob)
    return vec


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def sync_embeddings(db_path: Path) -> int:
    """Embed every chunk whose (text_hash, model) isn't already cached; return count newly embedded."""
    model = _load_model()
    with connect(db_path) as conn:
        _ensure_table(conn)
        rows = conn.execute(
            """
            SELECT c.text_hash, c.text FROM chunks c
            LEFT JOIN chunk_embeddings e ON e.text_hash = c.text_hash AND e.model = ?
            WHERE e.text_hash IS NULL
            """,
            (MODEL_NAME,),
        ).fetchall()
        if not rows:
            return 0
        texts = [row["text"] for row in rows]
        vectors = list(model.embed(texts))
        for row, vector in zip(rows, vectors):
            conn.execute(
                "INSERT OR REPLACE INTO chunk_embeddings(text_hash, model, vector) VALUES (?, ?, ?)",
                (row["text_hash"], MODEL_NAME, _pack(vector)),
            )
        return len(rows)


def semantic_search(
    db_path: Path,
    query: str,
    *,
    limit: int = 10,
    client: str = "cabal",
    entrypoint: str = "cli",
    usage_path: Path | None = None,
    record_usage: bool = True,
) -> list[dict[str, Any]]:
    """Embed query, sync missing chunk embeddings, and return top concepts by cosine similarity."""
    started = time.perf_counter()
    model = _load_model()
    sync_embeddings(db_path)
    query_vector = next(iter(model.embed([query])))

    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.type, c.title, c.resource, ch.text, e.vector
            FROM chunk_embeddings e
            JOIN chunks ch ON ch.text_hash = e.text_hash
            JOIN concepts c ON c.id = ch.concept_id
            WHERE e.model = ?
            """,
            (MODEL_NAME,),
        ).fetchall()

    scored: dict[str, dict[str, Any]] = {}
    for row in rows:
        score = _cosine(query_vector, _unpack(row["vector"]))
        existing = scored.get(row["id"])
        if existing is None or score > existing["score"]:
            snippet = row["text"][:200]
            scored[row["id"]] = {
                "id": row["id"],
                "type": row["type"],
                "title": row["title"],
                "resource": row["resource"],
                "snippet": snippet,
                "score": round(score, 4),
            }

    results = sorted(scored.values(), key=lambda item: item["score"], reverse=True)[:limit]

    if record_usage:
        append_usage(
            action="okf_semantic_search",
            query=query,
            budget="none",
            client=client,
            entrypoint=entrypoint,
            included_concepts=[item["id"] for item in results],
            estimated_tokens=round(sum(len(item["snippet"]) for item in results) / 4),
            duration_ms=round((time.perf_counter() - started) * 1000),
            usage_path=usage_path,
        )
    return results
