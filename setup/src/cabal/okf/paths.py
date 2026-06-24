"""Path and secret-safety helpers for OKF generation."""

from __future__ import annotations

import re
from pathlib import Path


_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{24,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
)


def normalize_resource(value: str | Path) -> str:
    raw = str(value).replace("\\", "/").strip()
    if raw.startswith("./"):
        raw = raw[2:]
    path = Path(raw)
    if path.is_absolute() or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError(f"Resource path must be repository-relative: {value}")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError(f"Resource path must not contain '..': {value}")
    return "/".join(parts)


def to_resource(root: Path, path: Path) -> str:
    root = root.resolve()
    path = path.resolve()
    try:
        rel = path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path is outside repository root: {path}") from exc
    return normalize_resource(rel)


def resource_path(root: Path, resource: str) -> Path:
    normalized = normalize_resource(resource)
    return root / Path(normalized)


def has_secret_value(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def safe_excerpt(text: str, fallback: str = "Generated from source metadata.") -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "---" or has_secret_value(stripped):
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        if stripped:
            return stripped[:180]
    return fallback
