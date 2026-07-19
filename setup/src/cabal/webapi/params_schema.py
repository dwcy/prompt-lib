"""Dependency-free validator for the JSON-schema subset used by ActionDescriptor.params_schema."""

from __future__ import annotations

from typing import Any

_TYPE_CHECKS = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}


def validate_params(params: Any, schema: dict) -> list[str]:
    """Return human-readable violations of the descriptor schema (empty list = valid)."""
    errors: list[str] = []
    _validate(params, schema, "params", errors)
    return errors


def _validate(value: Any, schema: dict, path: str, errors: list[str]) -> None:
    declared = schema.get("type")
    if declared is not None and not _matches_type(value, declared):
        errors.append(f"{path}: expected type {declared!r}")
        return
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", ()):
            if key not in value:
                errors.append(f"{path}.{key}: required property missing")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key}: additional property not allowed")
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], f"{path}.{key}", errors)
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate(item, item_schema, f"{path}[{index}]", errors)


def _matches_type(value: Any, declared: str | list[str]) -> bool:
    names = [declared] if isinstance(declared, str) else list(declared)
    return any(_TYPE_CHECKS.get(name, lambda _value: True)(value) for name in names)
