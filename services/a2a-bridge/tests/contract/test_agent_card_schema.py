"""Contract tests for the AgentCard model + builder (T016).

These tests pin the wire-format of every Agent Card the bridge ever serves,
per ``contracts/agent-card.schema.json``: the schema is JSON Schema draft
2020-12 with ``additionalProperties: false`` everywhere, ``protocols`` is
restricted to ``["json-rpc-2.0"]``, ``url`` must match
``^http://127\\.0\\.0\\.1:\\d+$`` (FR-009 localhost-only), and the
``capabilities`` / ``authentication`` constants are fixed for v1.

Per Constitution Principle III, this file lands BEFORE its implementation
(T017). Until then every test is expected to fail with ImportError on
``a2a_bridge.protocol.agent_card``.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

_DEFAULT_SKILL = {
    "id": "claude-prompt",
    "name": "Claude prompt",
    "description": "Run a prompt through Claude Code",
    "input_modes": ["text/plain"],
    "output_modes": ["text/plain"],
}

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "specs"
    / "001-a2a-bridge"
    / "contracts"
    / "agent-card.schema.json"
)


def _import_agent_card():
    from a2a_bridge.protocol import agent_card

    return agent_card


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _build_default_card():
    agent_card = _import_agent_card()
    return agent_card.build_agent_card(
        name="claude-code-a2a-adapter",
        host="127.0.0.1",
        port=8765,
        skills=[_DEFAULT_SKILL],
    )


def _card_to_dict(card) -> dict:
    if hasattr(card, "model_dump"):
        return card.model_dump(mode="json")
    return card.to_dict()


# ---------------------------------------------------------------------------
# Builder produces a schema-conformant card
# ---------------------------------------------------------------------------


class TestBuilderProducesSchemaConformantCard:
    def test_built_claude_card_validates_against_schema(self):
        agent_card = _import_agent_card()

        card = _build_default_card()

        assert agent_card.validate_against_schema(_card_to_dict(card)) is None

    def test_built_gemini_card_validates_against_schema(self):
        agent_card = _import_agent_card()

        card = agent_card.build_agent_card(
            name="gemini-a2a-adapter",
            host="127.0.0.1",
            port=8766,
            skills=[
                {
                    "id": "gemini-prompt",
                    "name": "Gemini prompt",
                    "description": "Run a prompt through the Gemini CLI",
                    "input_modes": ["text/plain"],
                    "output_modes": ["text/plain"],
                }
            ],
        )

        assert agent_card.validate_against_schema(_card_to_dict(card)) is None


# ---------------------------------------------------------------------------
# Field-by-field invariants
# ---------------------------------------------------------------------------


class TestBuilderConstantFields:
    def test_url_is_localhost_with_configured_port(self):
        card = _build_default_card()

        assert _card_to_dict(card)["url"] == "http://127.0.0.1:8765"

    def test_protocols_is_jsonrpc_2_0_only(self):
        card = _build_default_card()

        assert _card_to_dict(card)["protocols"] == ["json-rpc-2.0"]

    def test_capabilities_match_v1_constants(self):
        card = _build_default_card()

        assert _card_to_dict(card)["capabilities"] == {
            "streaming": True,
            "push_notifications": False,
            "state_history": False,
        }

    def test_authentication_schemes_is_bearer_only(self):
        card = _build_default_card()

        assert _card_to_dict(card)["authentication"]["schemes"] == ["bearer"]

    def test_version_defaults_to_1_0_0(self):
        card = _build_default_card()

        assert _card_to_dict(card)["version"] == "1.0.0"

    def test_name_is_echoed_from_builder_input(self):
        card = _build_default_card()

        assert _card_to_dict(card)["name"] == "claude-code-a2a-adapter"

    def test_skills_are_echoed_from_builder_input(self):
        card = _build_default_card()

        assert _card_to_dict(card)["skills"] == [_DEFAULT_SKILL]


# ---------------------------------------------------------------------------
# Negative-path schema enforcement
# ---------------------------------------------------------------------------


class TestSchemaRejectsInvalidCards:
    def test_missing_required_fields_raises_validation_error(self):
        agent_card = _import_agent_card()

        with pytest.raises(jsonschema.ValidationError):
            agent_card.validate_against_schema({"name": "x"})

    def test_grpc_protocol_is_rejected(self):
        agent_card = _import_agent_card()

        card = _card_to_dict(_build_default_card())
        card["protocols"] = ["grpc"]

        with pytest.raises(jsonschema.ValidationError):
            agent_card.validate_against_schema(card)

    def test_extra_top_level_field_is_rejected(self):
        agent_card = _import_agent_card()

        card = _card_to_dict(_build_default_card())
        card["foo"] = "bar"

        with pytest.raises(jsonschema.ValidationError):
            agent_card.validate_against_schema(card)

    def test_non_localhost_url_is_rejected(self):
        agent_card = _import_agent_card()

        card = _card_to_dict(_build_default_card())
        card["url"] = "https://example.com:8765"

        with pytest.raises(jsonschema.ValidationError):
            agent_card.validate_against_schema(card)

    def test_empty_skills_array_is_rejected(self):
        agent_card = _import_agent_card()

        card = _card_to_dict(_build_default_card())
        card["skills"] = []

        with pytest.raises(jsonschema.ValidationError):
            agent_card.validate_against_schema(card)

    def test_unknown_authentication_scheme_is_rejected(self):
        agent_card = _import_agent_card()

        card = _card_to_dict(_build_default_card())
        card["authentication"] = {"schemes": ["oauth2"]}

        with pytest.raises(jsonschema.ValidationError):
            agent_card.validate_against_schema(card)

    def test_invalid_version_format_is_rejected(self):
        agent_card = _import_agent_card()

        card = _card_to_dict(_build_default_card())
        card["version"] = "not-semver"

        with pytest.raises(jsonschema.ValidationError):
            agent_card.validate_against_schema(card)


# ---------------------------------------------------------------------------
# Schema file is the on-disk source of truth
# ---------------------------------------------------------------------------


class TestSchemaFileIsAuthoritative:
    def test_schema_file_exists_at_known_path(self):
        assert _SCHEMA_PATH.exists(), f"schema not found at {_SCHEMA_PATH}"

    def test_schema_declares_draft_2020_12(self):
        schema = _load_schema()

        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def test_schema_forbids_additional_top_level_properties(self):
        schema = _load_schema()

        assert schema["additionalProperties"] is False
