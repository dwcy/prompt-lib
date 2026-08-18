# -*- coding: utf-8 -*-
"""Route stage: decide whether a request is a question or a change before spending anything.

Most turns are not edits, and paying full agentic cost to answer "what does this handler do?" is
where naive pipelines burn money. This is a classification, so it binds to the cheapest model
available (FR-010, SC-009).

Safety default: an unparseable or failed classification resolves to QUESTION. Guessing CHANGE
would let an ambiguous reply start writing code; guessing QUESTION merely answers something the
developer can re-ask. The cheap mistake is the right default.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from cabal.dotnetgen.providers.base import (
    CompletionRequest,
    Message,
    Provider,
    ProviderError,
)

MAX_CLASSIFY_TOKENS: Final[int] = 8

INSTRUCTIONS: Final[str] = (
    "You classify a developer's request about a .NET codebase.\n"
    "Answer with exactly one word:\n"
    "  CHANGE   - they want code created, modified, deleted, or refactored\n"
    "  QUESTION - they want an explanation, a location, or a review; nothing is to be written\n"
    "Answer with the single word and nothing else."
)


class Intent(str, Enum):
    """What the developer asked for."""

    QUESTION = "question"
    CHANGE = "change"

    @property
    def enters_pipeline(self) -> bool:
        return self is Intent.CHANGE


class Classification:
    """Namespace for the parse rules, kept separate so they can be unit-tested directly."""

    CHANGE_TOKEN: Final[str] = "CHANGE"
    QUESTION_TOKEN: Final[str] = "QUESTION"

    @staticmethod
    def parse(reply: str) -> Intent:
        """Map a model reply onto an intent, defaulting to QUESTION when unclear."""
        upper = reply.strip().upper()
        if not upper:
            return Intent.QUESTION

        first = upper.split()[0].strip(".,:;!\"'`*")
        if first == Classification.CHANGE_TOKEN:
            return Intent.CHANGE
        if first == Classification.QUESTION_TOKEN:
            return Intent.QUESTION

        # A verbose reply still counts if it names exactly one token unambiguously.
        has_change = Classification.CHANGE_TOKEN in upper
        has_question = Classification.QUESTION_TOKEN in upper
        if has_change and not has_question:
            return Intent.CHANGE
        return Intent.QUESTION


def build_request(text: str, model: str) -> CompletionRequest:
    """The classification prompt. Deliberately tiny: this stage must never dominate cost."""
    return CompletionRequest(
        messages=(
            Message(role="system", content=INSTRUCTIONS),
            Message(role="user", content=text),
        ),
        model=model,
        max_output_tokens=MAX_CLASSIFY_TOKENS,
        temperature=0.0,
    )


def classify(text: str, provider: Provider, model: str) -> Intent:
    """Classify one request. A provider failure resolves to QUESTION rather than propagating."""
    try:
        result = provider.complete(build_request(text, model))
    except ProviderError:
        return Intent.QUESTION
    return Classification.parse(result.text)
