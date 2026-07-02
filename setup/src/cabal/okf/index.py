"""SQLite-backed OKF search index."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from cabal.okf.frontmatter import extract_frontmatter, parse_frontmatter


SCHEMA_VERSION = "2"


def default_index_path(bundle_root: Path) -> Path:
    return Path(bundle_root) / "index.sqlite"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _match_query(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+", query)
    if not tokens:
        return ""
    return " OR ".join(f'"{token}"' for token in tokens)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS metadata;
        DROP TABLE IF EXISTS edges;
        DROP TABLE IF EXISTS chunks;
        DROP TABLE IF EXISTS concepts;
        DROP TABLE IF EXISTS concept_fts;

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE concepts (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            resource TEXT NOT NULL,
            doc TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            body TEXT NOT NULL,
            body_hash TEXT NOT NULL
        );

        CREATE TABLE edges (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            target TEXT,
            target_ref TEXT NOT NULL,
            kind TEXT NOT NULL,
            confidence TEXT NOT NULL,
            reason TEXT NOT NULL,
            evidence_json TEXT NOT NULL
        );

        CREATE TABLE chunks (
            id TEXT PRIMARY KEY,
            concept_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            text TEXT NOT NULL,
            text_hash TEXT NOT NULL,
            FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE concept_fts USING fts5(
            id UNINDEXED,
            type UNINDEXED,
            title,
            description,
            resource,
            tags,
            body
        )
        """
    )


def _chunk_text(body: str, *, size: int = 900) -> list[str]:
    paragraphs = [part.strip() for part in body.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > size:
            chunks.append(current)
            current = paragraph
        else:
            current = paragraph if not current else current + "\n\n" + paragraph
    if current:
        chunks.append(current)
    return chunks or [body.strip()]


def _load_docs(bundle_root: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in sorted(Path(bundle_root).rglob("*.md")):
        rel = str(path.relative_to(bundle_root)).replace("\\", "/")
        text = path.read_text(encoding="utf-8", errors="replace")
        raw_frontmatter, body = extract_frontmatter(text)
        if not raw_frontmatter:
            continue
        frontmatter = parse_frontmatter(raw_frontmatter)
        concept_id = frontmatter.get("id")
        if not concept_id or concept_id in {"index:prompt-lib", "log:prompt-lib"}:
            continue
        docs.append(
            {
                "id": str(concept_id),
                "type": str(frontmatter.get("type") or ""),
                "title": str(frontmatter.get("title") or ""),
                "description": str(frontmatter.get("description") or ""),
                "resource": str(frontmatter.get("resource") or ""),
                "doc": rel,
                "tags": list(frontmatter.get("tags") or []),
                "body": body,
            }
        )
    return docs


def bundle_fingerprint(bundle_root: Path) -> str:
    """Hash of sorted (doc_id, body_hash) pairs — the bundle's current content fingerprint."""
    docs = _load_docs(Path(bundle_root))
    pairs = sorted((doc["id"], _hash(doc["body"])) for doc in docs)
    return _hash(json.dumps(pairs, sort_keys=True))


def build_index(bundle_root: Path, db_path: Path | None = None) -> Path:
    bundle_root = Path(bundle_root)
    db_path = Path(db_path or default_index_path(bundle_root))
    graph = json.loads((bundle_root / "graph.json").read_text(encoding="utf-8"))
    docs = _load_docs(bundle_root)
    fingerprint = _hash(json.dumps(sorted((doc["id"], _hash(doc["body"])) for doc in docs), sort_keys=True))
    with connect(db_path) as conn:
        _create_schema(conn)
        conn.execute("INSERT INTO metadata(key, value) VALUES (?, ?)", ("schema_version", SCHEMA_VERSION))
        conn.execute("INSERT INTO metadata(key, value) VALUES (?, ?)", ("bundle_root", str(bundle_root)))
        conn.execute("INSERT INTO metadata(key, value) VALUES (?, ?)", ("generated_at", graph.get("generated_at", "")))
        conn.execute("INSERT INTO metadata(key, value) VALUES (?, ?)", ("bundle_fingerprint", fingerprint))
        for doc in docs:
            conn.execute(
                """
                INSERT INTO concepts(id, type, title, description, resource, doc, tags_json, body, body_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc["id"],
                    doc["type"],
                    doc["title"],
                    doc["description"],
                    doc["resource"],
                    doc["doc"],
                    json.dumps(doc["tags"], sort_keys=True),
                    doc["body"],
                    _hash(doc["body"]),
                ),
            )
            conn.execute(
                """
                INSERT INTO concept_fts(id, type, title, description, resource, tags, body)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc["id"],
                    doc["type"],
                    doc["title"],
                    doc["description"],
                    doc["resource"],
                    " ".join(doc["tags"]),
                    doc["body"],
                ),
            )
            for ordinal, chunk in enumerate(_chunk_text(doc["body"])):
                conn.execute(
                    """
                    INSERT INTO chunks(id, concept_id, ordinal, text, text_hash)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (f"{doc['id']}:{ordinal}", doc["id"], ordinal, chunk, _hash(chunk)),
                )
        for edge in graph.get("edges", []):
            conn.execute(
                """
                INSERT INTO edges(id, source, target, target_ref, kind, confidence, reason, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.get("id"),
                    edge.get("source"),
                    edge.get("target"),
                    edge.get("target_ref"),
                    edge.get("kind"),
                    edge.get("confidence"),
                    edge.get("reason"),
                    json.dumps(edge.get("evidence", []), sort_keys=True),
                ),
            )
    return db_path


def search_index(db_path: Path, query: str, *, limit: int = 10, types: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    match_query = _match_query(query)
    if not match_query:
        return []
    with connect(db_path) as conn:
        where = "concept_fts MATCH ?"
        params: list[Any] = [match_query]
        if types:
            placeholders = ",".join("?" for _ in types)
            where += f" AND type IN ({placeholders})"
            params.extend(types)
        sql = f"""
            SELECT id, type, title, resource, snippet(concept_fts, 6, '[', ']', ' ... ', 12) AS snippet, rank
            FROM concept_fts
            WHERE {where}
            ORDER BY rank
            LIMIT ?
        """
        params.append(limit)
        return [dict(row) for row in conn.execute(sql, params)]


def fts_available(db_path: Path) -> bool:
    with connect(db_path) as conn:
        return _table_exists(conn, "concept_fts")
