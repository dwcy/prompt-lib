# -*- coding: utf-8 -*-
"""Regression tests: bands marked as cache checkpoints must reach the API as cache_control."""

from __future__ import annotations

from cabal.dotnetgen.providers.anthropic import _split_system
from cabal.dotnetgen.providers.base import CompletionRequest, Message


def _request(*messages: Message) -> CompletionRequest:
    return CompletionRequest(model="claude-sonnet-4", messages=list(messages))


def test_a_checkpointed_system_band_is_sent_as_an_ephemeral_cache_block() -> None:
    request = _request(
        Message(role="system", content="stable prefix", cache_checkpoint=True),
        Message(role="user", content="do the thing"),
    )

    system, _messages = _split_system(request)

    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_an_uncheckpointed_request_keeps_the_plain_string_system_payload() -> None:
    request = _request(
        Message(role="system", content="stable prefix"),
        Message(role="user", content="do the thing"),
    )

    system, _messages = _split_system(request)

    assert system == "stable prefix"


def test_a_checkpointed_user_message_carries_its_own_cache_block() -> None:
    request = _request(Message(role="user", content="big context", cache_checkpoint=True))

    _system, messages = _split_system(request)

    assert messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_an_uncheckpointed_user_message_stays_a_bare_string() -> None:
    request = _request(Message(role="user", content="short ask"))

    _system, messages = _split_system(request)

    assert messages[0]["content"] == "short ask"
