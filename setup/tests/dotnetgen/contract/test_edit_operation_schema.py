# -*- coding: utf-8 -*-
"""Contract test (T006) for the EditOperation wire format — the surface SC-003 is measured on.

Two halves. The schema-shape assertions lock the contract document itself. The enforcement
assertions drive raw wire payloads through `cabal.dotnetgen.edits.model`, and fail until T009
implements it — that is the Principle III "observed failing" state.
"""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

SYMBOL_OP = {
    "file": "src/Orders.Domain/Order.cs",
    "anchor_kind": "symbol",
    "symbol": "Orders.Domain.Order.Cancel(System.DateTimeOffset)",
    "disposition": "replace",
    "content": "public void Cancel(DateTimeOffset at) { }",
}
TEXT_OP = {
    "file": "src/Orders.Api/Program.cs",
    "anchor_kind": "text",
    "search": "builder.Services.AddOpenApi();",
    "disposition": "replace",
    "content": "builder.Services.AddOpenApi();\nbuilder.Services.AddOrders();",
}
DELETE_OP = {
    "file": "src/Orders.Domain/Legacy.cs",
    "anchor_kind": "symbol",
    "symbol": "Orders.Domain.Legacy.Obsolete()",
    "disposition": "delete",
}
CREATE_OP = {
    "file": "src/Orders.Domain/Money.cs",
    "anchor_kind": "symbol",
    "symbol": "Orders.Domain.Money",
    "disposition": "create-file",
    "content": "namespace Orders.Domain;\n\npublic readonly record struct Money(decimal Amount);",
}


# --- schema document contract -------------------------------------------------------------


def test_schema_is_a_valid_draft_2020_12_schema(edit_operation_schema: dict) -> None:
    Draft202012Validator.check_schema(edit_operation_schema)


def test_schema_declares_no_line_number_field(edit_operation_schema: dict) -> None:
    """Line numbers are structurally excluded: models cannot count (research 1.2, 1.3)."""
    props = edit_operation_schema["properties"]
    assert "line" not in props
    assert "line_numbers" not in props
    assert not any("line" in name for name in props), sorted(props)


def test_schema_forbids_additional_properties(edit_operation_schema: dict) -> None:
    assert edit_operation_schema["additionalProperties"] is False


@pytest.mark.parametrize(
    "payload",
    [SYMBOL_OP, TEXT_OP, DELETE_OP, CREATE_OP],
    ids=["symbol-replace", "text-replace", "symbol-delete", "create-file"],
)
def test_schema_accepts_valid_operations(edit_operation_schema: dict, payload: dict) -> None:
    Draft202012Validator(edit_operation_schema).validate(payload)


@pytest.mark.parametrize(
    ("payload", "why"),
    [
        ({**SYMBOL_OP, "search": "x"}, "symbol and search are mutually exclusive"),
        ({**TEXT_OP, "symbol": "A.B.C()"}, "text anchor must not carry a symbol"),
        ({k: v for k, v in SYMBOL_OP.items() if k != "symbol"}, "symbol anchor requires symbol"),
        ({k: v for k, v in TEXT_OP.items() if k != "search"}, "text anchor requires search"),
        ({**DELETE_OP, "content": "anything"}, "delete must not carry content"),
        ({k: v for k, v in SYMBOL_OP.items() if k != "content"}, "replace requires content"),
        ({**SYMBOL_OP, "lines": [1, 2]}, "unknown properties are rejected"),
        ({**SYMBOL_OP, "disposition": "patch"}, "disposition is a closed set"),
        ({**SYMBOL_OP, "anchor_kind": "regex"}, "anchor_kind is a closed set"),
    ],
)
def test_schema_rejects_invalid_operations(
    edit_operation_schema: dict, payload: dict, why: str
) -> None:
    validator = Draft202012Validator(edit_operation_schema)
    assert not validator.is_valid(payload), why


# --- enforcement contract (fails until T009) ----------------------------------------------


@pytest.fixture
def model():
    """Import the model directly. Until T009 lands this raises, and these tests go red by design."""
    import cabal.dotnetgen.edits.model as edit_model

    return edit_model


@pytest.mark.parametrize(
    "payload",
    [SYMBOL_OP, TEXT_OP, DELETE_OP, CREATE_OP],
    ids=["symbol-replace", "text-replace", "symbol-delete", "create-file"],
)
def test_model_parses_valid_wire_payloads(model, payload: dict) -> None:
    op = model.parse_operation(payload)
    assert op.file == payload["file"]
    assert op.disposition == payload["disposition"]


def test_model_rejects_schema_violations(model) -> None:
    with pytest.raises(model.EditOperationError):
        model.parse_operation({**SYMBOL_OP, "search": "x"})


def test_model_rejects_lazy_placeholder_content(model) -> None:
    """A '... unchanged ...' stub is a contract violation, not lazy output to tolerate."""
    lazy = {**SYMBOL_OP, "content": "public void Cancel() {\n    // ... rest of method unchanged\n}"}
    with pytest.raises(model.EditOperationError):
        model.parse_operation(lazy)


def test_model_rejects_noop_rewrite(model) -> None:
    """Re-emitting identical text wastes output tokens and invites unrelated cleanup."""
    existing = SYMBOL_OP["content"]
    with pytest.raises(model.EditOperationError):
        model.parse_operation(SYMBOL_OP, existing_text=existing)


def test_model_accepts_real_change_against_existing_text(model) -> None:
    op = model.parse_operation(SYMBOL_OP, existing_text="public void Cancel(DateTimeOffset at) { throw new NotSupportedException(); }")
    assert op.content == SYMBOL_OP["content"]


def test_model_and_schema_agree_on_every_payload(model, edit_operation_schema: dict) -> None:
    """Drift guard: the hand-rolled validator must accept exactly what the schema accepts.

    `model.py` deliberately does not import jsonschema, so this is what keeps the runtime
    validator and the published contract from diverging.
    """
    validator = Draft202012Validator(edit_operation_schema)
    corpus = [
        SYMBOL_OP,
        TEXT_OP,
        DELETE_OP,
        CREATE_OP,
        {**SYMBOL_OP, "search": "x"},
        {**TEXT_OP, "symbol": "A.B.C()"},
        {k: v for k, v in SYMBOL_OP.items() if k != "symbol"},
        {k: v for k, v in TEXT_OP.items() if k != "search"},
        {**DELETE_OP, "content": "anything"},
        {k: v for k, v in SYMBOL_OP.items() if k != "content"},
        {**SYMBOL_OP, "lines": [1, 2]},
        {**SYMBOL_OP, "disposition": "patch"},
        {**SYMBOL_OP, "anchor_kind": "regex"},
        {**SYMBOL_OP, "reason": "traces to the approved intent"},
    ]

    disagreements = []
    for payload in corpus:
        schema_ok = validator.is_valid(payload)
        try:
            model.parse_operation(payload)
            model_ok = True
        except model.EditOperationError:
            model_ok = False
        if schema_ok != model_ok:
            disagreements.append((payload, schema_ok, model_ok))

    assert not disagreements, f"validator drift on {len(disagreements)} payload(s): {disagreements}"
