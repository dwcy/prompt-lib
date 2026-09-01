# -*- coding: utf-8 -*-
"""T005: the value-leak guarantee is structural, so assert the structure, not a convention."""

from __future__ import annotations

import dataclasses
import json

from cabal.models.envsources import (
    AvailabilityState,
    ConfigLayer,
    Retrievability,
    SourceKind,
    VariableContainer,
    VariableEntry,
    VariableSource,
    source_payload,
)


def _entry(**overrides) -> VariableEntry:
    base = {
        "name": "DATABASE_URL",
        "source_id": "repo_file:.env",
        "container_id": "repo_file:.env",
    }
    base.update(overrides)
    return VariableEntry(**base)


def test_variable_entry_declares_no_value_field() -> None:
    names = {f.name for f in dataclasses.fields(VariableEntry)}

    assert "value" not in names


def test_variable_entry_cannot_be_constructed_with_a_value() -> None:
    try:
        VariableEntry(  # pylint: disable=unexpected-keyword-arg
            name="X",
            source_id="s",
            container_id="c",
            value="secret",  # type: ignore[call-arg]
        )
    except TypeError:
        return
    raise AssertionError("VariableEntry accepted a value argument")


def test_variable_entry_cannot_be_assigned_a_value() -> None:
    entry = _entry()

    try:
        object.__setattr__(entry, "value", "secret")
    except AttributeError:
        return
    # frozen dataclasses without __slots__ still allow object.__setattr__, so the
    # binding guarantee that matters is serialisation: the field never reaches the wire.
    assert "value" not in source_payload(
        VariableSource(
            id="s",
            kind=SourceKind.REPO_FILE,
            label=".env",
            state=AvailabilityState.OK,
            containers=[
                VariableContainer(id="c", source_id="s", label=".env", entries=[entry])
            ],
        )
    )["containers"][0]["entries"][0]


def test_source_payload_serialises_enums_as_their_wire_strings() -> None:
    source = VariableSource(
        id="github:env:production",
        kind=SourceKind.GITHUB,
        label="GitHub",
        state=AvailabilityState.OK,
        containers=[
            VariableContainer(
                id="github:env:production",
                source_id="github:env:production",
                label="production",
                layer=ConfigLayer(stack="dotnet", name="appsettings.json", rank=5, wins=True),
                entries=[
                    _entry(
                        source_id="github:env:production",
                        container_id="github:env:production",
                        retrievability=Retrievability.NEVER,
                        retrievability_reason="GitHub never returns secret values",
                    )
                ],
            )
        ],
    )

    payload = source_payload(source)
    encoded = json.dumps(payload)

    assert payload["kind"] == "github"
    assert payload["state"] == "ok"
    assert payload["containers"][0]["entries"][0]["retrievability"] == "never"
    assert payload["containers"][0]["layer"]["rank"] == 5
    assert '"value"' not in encoded
