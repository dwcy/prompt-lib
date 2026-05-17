"""Trigger Protocol and ``TriggerEvent`` model (T011).

Per research.md R5 and data-model.md § TriggerEvent: triggers are async
iterators of ``TriggerEvent`` records. ``Trigger`` is a structural Protocol
so any class with the matching method signatures qualifies — no inheritance.
The Protocol is ``@runtime_checkable`` so callers can assert conformance via
``isinstance`` in tests and bootstrap code.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

_REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_HEAD_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class TriggerEvent(BaseModel):
    """A normalized event emitted by a ``Trigger`` source.

    Pure in-memory; never persisted directly. Frozen + ``extra='forbid'`` so
    payloads are immutable and unknown fields fail fast at construction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["pr.opened", "pr.updated", "issue.opened"]
    repo: str
    pr_number: int
    head_sha: str
    detected_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("repo")
    @classmethod
    def _validate_repo(cls, value: str) -> str:
        if not _REPO_SLUG_RE.match(value):
            raise ValueError("repo must match '<owner>/<repo>'")
        return value

    @field_validator("pr_number")
    @classmethod
    def _validate_pr_number(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("pr_number must be > 0")
        return value

    @field_validator("head_sha")
    @classmethod
    def _validate_head_sha(cls, value: str) -> str:
        if not _HEAD_SHA_RE.match(value):
            raise ValueError("head_sha must be a 40-char lowercase hex string")
        return value

    @field_validator("detected_at")
    @classmethod
    def _validate_detected_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("detected_at must be timezone-aware")
        return value


@runtime_checkable
class Trigger(Protocol):
    """Structural contract every trigger source must satisfy.

    v1 ships exactly one implementation: ``GithubPollTrigger``. v2 will add
    ``GithubWebhookTrigger``. Both are interchangeable to ``daemon.py``.
    """

    async def events(self) -> AsyncIterator[TriggerEvent]:
        ...

    async def aclose(self) -> None: ...
