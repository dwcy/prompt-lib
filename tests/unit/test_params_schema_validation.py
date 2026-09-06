"""Unit tests for the params_schema validator's enum and numeric-bound enforcement."""

from __future__ import annotations

from cabal.webapi.params_schema import validate_params

_SCOPE_SCHEMA = {
    "type": "object",
    "properties": {"scope": {"type": "string", "enum": ["global", "local"]}},
    "required": ["scope"],
    "additionalProperties": False,
}

_PORT_SCHEMA = {
    "type": "object",
    "properties": {"port": {"type": "integer", "minimum": 1, "maximum": 65535}},
    "required": ["port"],
    "additionalProperties": False,
}


def test_enum_member_passes_validation():
    assert validate_params({"scope": "global"}, _SCOPE_SCHEMA) == []


def test_value_outside_declared_enum_is_rejected():
    errors = validate_params({"scope": "system"}, _SCOPE_SCHEMA)

    assert errors and "params.scope" in errors[0]


def test_number_below_minimum_is_rejected():
    errors = validate_params({"port": 0}, _PORT_SCHEMA)

    assert errors and "minimum" in errors[0]


def test_number_above_maximum_is_rejected():
    errors = validate_params({"port": 99999999}, _PORT_SCHEMA)

    assert errors and "maximum" in errors[0]


def test_boolean_is_not_coerced_into_numeric_bounds():
    schema = {
        "type": "object",
        "properties": {"flag": {"type": "boolean", "minimum": 5}},
        "additionalProperties": False,
    }

    assert validate_params({"flag": True}, schema) == []
