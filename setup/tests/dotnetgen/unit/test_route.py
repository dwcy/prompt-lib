# -*- coding: utf-8 -*-
"""Unit tests (T022) for the route stage: question vs change, and its safety default."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from cabal.dotnetgen.providers.base import (
    CompletionRequest,
    CompletionResult,
    ProviderError,
    ProviderStatus,
    Usage,
)
from cabal.dotnetgen.stages import route


@dataclass
class StubProvider:
    """Returns a canned reply, or raises, so classification is tested without a model."""

    reply: str = "CHANGE"
    error: Exception | None = None
    name: str = "stub"
    seen: list[CompletionRequest] | None = None

    def complete(self, request: CompletionRequest) -> CompletionResult:
        if self.seen is not None:
            self.seen.append(request)
        if self.error is not None:
            raise self.error
        return CompletionResult(
            text=self.reply, usage=Usage(), model=request.model, provider=self.name
        )

    def check(self) -> ProviderStatus:
        return ProviderStatus(self.name, "stub-model", reachable=True)


# --- parsing -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    ["CHANGE", "change", " Change ", "CHANGE.", "**CHANGE**", "CHANGE\n"],
    ids=["plain", "lower", "padded", "punctuated", "emphasised", "trailing-newline"],
)
def test_change_replies_are_recognised(reply: str) -> None:
    assert route.Classification.parse(reply) is route.Intent.CHANGE


@pytest.mark.parametrize(
    "reply",
    ["QUESTION", "question", "QUESTION:", "  QUESTION"],
    ids=["plain", "lower", "punctuated", "padded"],
)
def test_question_replies_are_recognised(reply: str) -> None:
    assert route.Classification.parse(reply) is route.Intent.QUESTION


def test_verbose_reply_naming_only_change_is_recognised() -> None:
    assert route.Classification.parse("This is a CHANGE request.") is route.Intent.CHANGE


def test_ambiguous_reply_naming_both_defaults_to_question() -> None:
    """The cheap mistake is answering something re-askable, not writing unwanted code."""
    assert route.Classification.parse("either QUESTION or CHANGE") is route.Intent.QUESTION


@pytest.mark.parametrize(
    "reply", ["", "   ", "maybe", "I am not sure", "42"], ids=["empty", "blank", "word", "sentence", "number"]
)
def test_unparseable_reply_defaults_to_question(reply: str) -> None:
    assert route.Classification.parse(reply) is route.Intent.QUESTION


# --- classification ------------------------------------------------------------------------


def test_change_request_is_classified_as_change() -> None:
    provider = StubProvider(reply="CHANGE")

    assert route.classify("add a cancel endpoint", provider, "m") is route.Intent.CHANGE


def test_question_request_is_classified_as_question() -> None:
    provider = StubProvider(reply="QUESTION")

    assert route.classify("what does this handler do?", provider, "m") is route.Intent.QUESTION


def test_provider_failure_resolves_to_question() -> None:
    """A failed classification must never open the write path."""
    provider = StubProvider(error=ProviderError("endpoint down"))

    assert route.classify("add an endpoint", provider, "m") is route.Intent.QUESTION


def test_only_change_enters_the_pipeline() -> None:
    assert (route.Intent.CHANGE.enters_pipeline, route.Intent.QUESTION.enters_pipeline) == (True, False)


# --- cost shape ----------------------------------------------------------------------------


def test_classification_caps_output_tokens_tightly() -> None:
    """Routing exists to avoid spending; it must not become a cost centre itself."""
    request = route.build_request("add an endpoint", "m")

    assert request.max_output_tokens == route.MAX_CLASSIFY_TOKENS


def test_classification_is_deterministic() -> None:
    request = route.build_request("add an endpoint", "m")

    assert request.temperature == 0.0


def test_classification_sends_only_instructions_and_the_request() -> None:
    seen: list[CompletionRequest] = []
    route.classify("add an endpoint", StubProvider(seen=seen), "m")

    assert [m.role for m in seen[0].messages] == ["system", "user"]
