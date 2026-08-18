# -*- coding: utf-8 -*-
"""Unit tests (T021) for cache-ordered prompt assembly and locked per-project state."""

from __future__ import annotations

from pathlib import Path

import pytest

from cabal.dotnetgen import state
from cabal.dotnetgen.context import bands
from cabal.dotnetgen.providers.base import Message

INSTRUCTIONS = "You write C# for a locked architecture template."
RULES = ["one type per file", "commands mutate, queries return"]
TEMPLATE_CONTRACT = "template: vertical-slice"
STRUCTURAL_MAP = "class Order { public void Cancel(); }"


def _full_prompt() -> tuple[bands.BandedMessage, ...]:
    return bands.build(
        instructions=INSTRUCTIONS,
        rules=RULES,
        template_contract=TEMPLATE_CONTRACT,
        structural_map=STRUCTURAL_MAP,
        opened_files=[bands.OpenedFile("src/Order.cs", "// body")],
        transient=[Message(role="user", content="add a cancel endpoint")],
    )


# --- band ordering -------------------------------------------------------------------------


def test_assembled_bands_run_stable_to_volatile() -> None:
    ordered = [entry.band for entry in _full_prompt()]

    assert ordered == sorted(ordered)


def test_instructions_come_before_everything_else() -> None:
    first = _full_prompt()[0]

    assert first.band == bands.BAND_INSTRUCTIONS


def test_transient_content_comes_last() -> None:
    last = _full_prompt()[-1]

    assert last.band == bands.BAND_TRANSIENT


def test_rules_and_map_each_carry_a_cache_checkpoint() -> None:
    checkpointed = {e.band for e in _full_prompt() if e.message.cache_checkpoint}

    assert checkpointed == {bands.BAND_RULES, bands.BAND_MAP}


def test_opened_file_contents_carry_no_checkpoint() -> None:
    """Band 4 changes every run; checkpointing it would write a cache entry that never hits."""
    files_band = [e for e in _full_prompt() if e.band == bands.BAND_FILES]

    assert all(not e.message.cache_checkpoint for e in files_band)


def test_empty_bands_are_omitted_rather_than_padded() -> None:
    minimal = bands.build(instructions=INSTRUCTIONS)

    assert [e.band for e in minimal] == [bands.BAND_INSTRUCTIONS]


def test_cacheable_prefix_ends_at_the_last_checkpoint() -> None:
    prompt = _full_prompt()

    prefix = bands.cacheable_prefix(prompt)

    assert prefix[-1].content == STRUCTURAL_MAP


def test_prompt_without_checkpoints_has_no_cacheable_prefix() -> None:
    minimal = bands.build(instructions=INSTRUCTIONS)

    assert bands.cacheable_prefix(minimal) == ()


def test_out_of_order_bands_are_rejected() -> None:
    scrambled = [
        bands.BandedMessage(bands.BAND_TRANSIENT, Message(role="user", content="diagnostic")),
        bands.BandedMessage(bands.BAND_RULES, Message(role="system", content="rules")),
    ]

    with pytest.raises(bands.BandOrderError):
        bands._assert_ordering(scrambled)


# --- project state -------------------------------------------------------------------------


def test_creating_a_project_records_the_chosen_template(solution_dir: Path) -> None:
    created = state.create(solution_dir, "vertical-slice")

    assert created.template_id == "vertical-slice"


def test_recorded_template_survives_a_reload(solution_dir: Path) -> None:
    state.create(solution_dir, "clean-arch")

    assert state.load(solution_dir).template_id == "clean-arch"


def test_unknown_template_is_refused_at_creation(solution_dir: Path) -> None:
    with pytest.raises(state.StateError):
        state.create(solution_dir, "hexagonal")


def test_creating_twice_is_refused(solution_dir: Path) -> None:
    state.create(solution_dir, "minimal-service")

    with pytest.raises(state.TemplateLockError):
        state.create(solution_dir, "minimal-service")


def test_changing_the_template_is_refused_not_migrated(solution_dir: Path) -> None:
    created = state.create(solution_dir, "minimal-service")

    with pytest.raises(state.TemplateLockError):
        state.save(solution_dir, type(created)(**{**created.to_dict(), "template_id": "clean-arch"}))


def test_requesting_a_different_template_is_refused(solution_dir: Path) -> None:
    state.create(solution_dir, "vertical-slice")

    with pytest.raises(state.TemplateLockError):
        state.assert_template(solution_dir, "clean-arch")


def test_requesting_the_recorded_template_is_allowed(solution_dir: Path) -> None:
    state.create(solution_dir, "vertical-slice")

    assert state.assert_template(solution_dir, "vertical-slice").template_id == "vertical-slice"


def test_loading_a_project_that_was_never_created_is_an_error(solution_dir: Path) -> None:
    with pytest.raises(state.StateError):
        state.load(solution_dir)


def test_map_fingerprint_is_recorded_without_touching_the_template(solution_dir: Path) -> None:
    state.create(solution_dir, "vertical-slice")

    updated = state.record_map(solution_dir, "sha256:abc")

    assert (updated.map_fingerprint, updated.template_id) == ("sha256:abc", "vertical-slice")


def test_unchanged_solution_shape_yields_the_same_fingerprint() -> None:
    shape = {"src/Order.cs": 120, "src/Money.cs": 40}

    assert state.structural_fingerprint(shape) == state.structural_fingerprint(dict(reversed(list(shape.items()))))


def test_changed_solution_shape_yields_a_different_fingerprint() -> None:
    before = state.structural_fingerprint({"src/Order.cs": 120})

    assert before != state.structural_fingerprint({"src/Order.cs": 121})


def test_touched_types_are_ordered_most_recent_first(solution_dir: Path) -> None:
    state.create(solution_dir, "vertical-slice")
    state.touch_types(solution_dir, ("Order",))

    updated = state.touch_types(solution_dir, ("Money",))

    assert updated.recent_types == ("Money", "Order")


def test_recency_list_is_bounded(solution_dir: Path) -> None:
    state.create(solution_dir, "vertical-slice")

    updated = state.touch_types(solution_dir, tuple(f"Type{i}" for i in range(state.RECENT_TYPES_LIMIT + 10)))

    assert len(updated.recent_types) == state.RECENT_TYPES_LIMIT
