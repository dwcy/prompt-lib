# -*- coding: utf-8 -*-
"""Contract test (T007) for the RunRecord wire format — the cost ledger every success criterion reads.

This locks the contract document. The producer-side assertions (that a real run emits a record
satisfying it, reconciled to within 5%) belong to the ledger tasks in Phase 7 and extend this file.
"""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

MINIMAL = {
    "run_id": "r-0001",
    "outcome": "completed",
    "stage_costs": {
        "architect": {"provider": "cli_shell", "model": "claude-opus-5"},
        "write": {"provider": "openai_compatible", "model": "qwen2.5-coder:7b"},
    },
    "retry_budget": {"ceiling": 3, "consumed": 0},
    "wall_clock_seconds": 42.0,
}

FULL = {
    **MINIMAL,
    "project_path": "C:/work/orders",
    "template_id": "vertical-slice",
    "repair_attempts": [
        {"attempt": 1, "classification": "code_defect", "diagnostic_ids": ["CS0246"], "cost_usd": 0.01, "resolved": True}
    ],
    "edit_applications": [
        {"file": "src/Orders.Domain/Order.cs", "anchor_kind": "symbol", "outcome": "applied", "relaxation_level": 0}
    ],
    "derived": {
        "cache_ratio": 0.78,
        "edit_success_rate": 1.0,
        "first_attempt_build_green": True,
        "initial_attempt_cost_usd": 0.03,
        "repair_cost_usd": 0.01,
        "reconciled": True,
    },
}


def test_schema_is_a_valid_draft_2020_12_schema(run_record_schema: dict) -> None:
    Draft202012Validator.check_schema(run_record_schema)


@pytest.mark.parametrize("payload", [MINIMAL, FULL], ids=["minimal", "full"])
def test_schema_accepts_valid_records(run_record_schema: dict, payload: dict) -> None:
    Draft202012Validator(run_record_schema).validate(payload)


def test_outcome_is_a_closed_set_of_four(run_record_schema: dict) -> None:
    outcomes = run_record_schema["properties"]["outcome"]["enum"]
    assert set(outcomes) == {
        "completed",
        "halted_at_ceiling",
        "aborted_environment",
        "rejected_at_gate",
    }


def test_verify_stage_needs_no_model_cost(run_record_schema: dict) -> None:
    """The .NET toolchain is the free signal; `verify` is present but carries no binding requirement."""
    stages = run_record_schema["properties"]["stage_costs"]["properties"]
    assert "verify" in stages


def test_zero_cost_is_representable_for_local_models(run_record_schema: dict) -> None:
    """SC-008 depends on a locally-hosted stage reporting exactly zero cost."""
    payload = {
        **MINIMAL,
        "stage_costs": {
            "write": {
                "provider": "openai_compatible",
                "model": "qwen2.5-coder:7b",
                "input_tokens": 8000,
                "cached_input_tokens": 6000,
                "output_tokens": 900,
                "cost_usd": 0.0,
            }
        },
    }
    Draft202012Validator(run_record_schema).validate(payload)


@pytest.mark.parametrize(
    ("payload", "why"),
    [
        ({**MINIMAL, "outcome": "kinda_done"}, "outcome is a closed set"),
        ({k: v for k, v in MINIMAL.items() if k != "retry_budget"}, "retry_budget is required"),
        ({k: v for k, v in MINIMAL.items() if k != "run_id"}, "run_id is required"),
        ({**MINIMAL, "retry_budget": {"ceiling": 3, "consumed": -1}}, "consumed cannot be negative"),
        ({**MINIMAL, "wall_clock_seconds": -1}, "wall clock cannot be negative"),
        ({**MINIMAL, "unexpected": 1}, "unknown properties are rejected"),
        ({**MINIMAL, "derived": {"cache_ratio": 1.5}}, "cache_ratio is a ratio"),
        ({**MINIMAL, "template_id": "hexagonal"}, "template_id is the closed set of three"),
    ],
)
def test_schema_rejects_invalid_records(run_record_schema: dict, payload: dict, why: str) -> None:
    assert not Draft202012Validator(run_record_schema).is_valid(payload), why


def test_ceiling_invariant_is_documented_not_schema_enforced(run_record_schema: dict) -> None:
    """`consumed <= ceiling` cannot be expressed in JSON Schema, so it is asserted in code.

    This test pins the contract's own admission of that, so the runtime check is never
    assumed to be covered by validation alone (SC-007 is enforced in the pipeline).
    """
    budget = run_record_schema["properties"]["retry_budget"]
    assert "consumed <= ceiling" in budget["$comment"]
