# -*- coding: utf-8 -*-
"""Cache-ordered prompt assembly: five bands, ordered stable to volatile.

A prompt cache is a *prefix* — anything that changes invalidates everything after it. So this
ordering is not cosmetic, it *is* the caching strategy, and getting it wrong is what turns a
70%+ cache ratio into single digits (research 1.6, R5).

    band 1  pipeline system prompt, stage instructions, edit-format contract   near-permanent
    band 2  csharp.md + _size-discipline.md rules, locked template contract    checkpoint
    band 3  structural map of the solution                                     checkpoint
    band 4  contents of files opened this run                                  volatile
    band 5  approved intent, prior diagnostics, repair history                 most volatile

Repair attempts append to band 5 only. A repair must never touch bands 1-3, which is a second,
independent reason diagnostics route back to the writing stage rather than the architect stage.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from cabal.dotnetgen.providers.base import Message

BAND_INSTRUCTIONS: Final[int] = 1
BAND_RULES: Final[int] = 2
BAND_MAP: Final[int] = 3
BAND_FILES: Final[int] = 4
BAND_TRANSIENT: Final[int] = 5

# Bands whose tail carries a cache checkpoint. Band 1 needs none: band 2's checkpoint covers
# the whole prefix up to that point.
CHECKPOINT_BANDS: Final[frozenset[int]] = frozenset({BAND_RULES, BAND_MAP})


class BandOrderError(ValueError):
    """Raised when assembled content would violate stable-to-volatile ordering."""


@dataclass(frozen=True)
class BandedMessage:
    """A message plus the band it belongs to, so ordering can be asserted rather than assumed."""

    band: int
    message: Message


@dataclass(frozen=True)
class OpenedFile:
    """One file's contents, supplied to band 4."""

    path: str
    text: str

    def render(self) -> str:
        return f"--- {self.path} ---\n{self.text}"


def _system(text: str, *, checkpoint: bool = False) -> Message:
    return Message(role="system", content=text, cache_checkpoint=checkpoint)


def _user(text: str, *, checkpoint: bool = False) -> Message:
    return Message(role="user", content=text, cache_checkpoint=checkpoint)


def build(
    *,
    instructions: str,
    rules: Sequence[str] = (),
    template_contract: str | None = None,
    structural_map: str | None = None,
    opened_files: Sequence[OpenedFile] = (),
    transient: Sequence[Message] = (),
) -> tuple[BandedMessage, ...]:
    """Assemble the banded prompt. Empty bands are omitted, never padded."""
    banded: list[BandedMessage] = [
        BandedMessage(BAND_INSTRUCTIONS, _system(instructions))
    ]

    band2_parts = [*rules]
    if template_contract:
        band2_parts.append(template_contract)
    if band2_parts:
        banded.append(
            BandedMessage(
                BAND_RULES,
                _system("\n\n".join(band2_parts), checkpoint=BAND_RULES in CHECKPOINT_BANDS),
            )
        )

    if structural_map:
        banded.append(
            BandedMessage(
                BAND_MAP,
                _user(structural_map, checkpoint=BAND_MAP in CHECKPOINT_BANDS),
            )
        )

    if opened_files:
        rendered = "\n\n".join(f.render() for f in opened_files)
        banded.append(BandedMessage(BAND_FILES, _user(rendered)))

    banded.extend(BandedMessage(BAND_TRANSIENT, m) for m in transient)

    _assert_ordering(banded)
    return tuple(banded)


def _assert_ordering(banded: Sequence[BandedMessage]) -> None:
    """Bands must be non-decreasing. A volatile item ahead of a stable one destroys the cache."""
    previous = 0
    for entry in banded:
        if entry.band < previous:
            raise BandOrderError(
                f"band {entry.band} appears after band {previous}; "
                "context must be ordered stable-to-volatile or the cache self-destructs"
            )
        previous = entry.band


def to_messages(banded: Sequence[BandedMessage]) -> tuple[Message, ...]:
    """Flatten to the provider-facing message tuple."""
    return tuple(entry.message for entry in banded)


def cacheable_prefix(banded: Sequence[BandedMessage]) -> tuple[Message, ...]:
    """The messages up to and including the last checkpoint — what a cache hit can cover."""
    last = -1
    for index, entry in enumerate(banded):
        if entry.message.cache_checkpoint:
            last = index
    if last < 0:
        return ()
    return tuple(entry.message for entry in banded[: last + 1])


def checkpoint_count(banded: Sequence[BandedMessage]) -> int:
    return sum(1 for entry in banded if entry.message.cache_checkpoint)
