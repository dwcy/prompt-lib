"""Small deterministic YAML frontmatter writer/parser for generated OKF files."""

from __future__ import annotations

from typing import Any


_ORDER = ("type", "title", "description", "resource", "tags", "timestamp", "id", "relations")


def _quote(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    needs_quote = any(ch in text for ch in (":", "#", "[", "]", "{", "}", '"', "'")) or text.lower() in {
        "true",
        "false",
        "null",
    }
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"' if needs_quote else escaped


def _write_value(lines: list[str], key: str, value: Any, indent: int = 0) -> None:
    prefix = " " * indent
    if isinstance(value, (list, tuple)):
        lines.append(f"{prefix}{key}:")
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{prefix}  -")
                for child_key in sorted(item):
                    _write_value(lines, child_key, item[child_key], indent + 4)
            else:
                lines.append(f"{prefix}  - {_quote(item)}")
    elif isinstance(value, dict):
        lines.append(f"{prefix}{key}:")
        for child_key in sorted(value):
            _write_value(lines, child_key, value[child_key], indent + 2)
    else:
        lines.append(f"{prefix}{key}: {_quote(value)}")


def dump_frontmatter(metadata: dict[str, Any]) -> str:
    lines: list[str] = []
    ordered = [key for key in _ORDER if key in metadata]
    ordered.extend(sorted(key for key in metadata if key not in ordered))
    for key in ordered:
        _write_value(lines, key, metadata[key])
    return "\n".join(lines) + "\n"


def dump_document(metadata: dict[str, Any], body: str) -> str:
    clean_body = body if body.endswith("\n") else body + "\n"
    return f"---\n{dump_frontmatter(metadata)}---\n\n{clean_body}"


def extract_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---", 4)
    if end == -1:
        return "", text
    frontmatter = text[4:end]
    body = text[end + len("\n---") :]
    if body.startswith("\n"):
        body = body[1:]
    return frontmatter, body


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value.isdigit():
        return int(value)
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def parse_frontmatter(frontmatter: str) -> dict[str, Any]:
    """Parse the generated subset: top-level scalars and scalar lists.

    Nested relation objects are intentionally left as raw list markers by MVP
    validation; graph.json is the authoritative machine-readable edge surface.
    """

    result: dict[str, Any] = {}
    current_list: str | None = None
    for line in frontmatter.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list:
            result.setdefault(current_list, []).append(_parse_scalar(line[4:]))
            continue
        if line.startswith(" "):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if value == "":
            result[key] = []
            current_list = key
        else:
            result[key] = _parse_scalar(value)
            current_list = None
    return result
