# -*- coding: utf-8 -*-
"""EditOperation: the validated boundary between the writing stage and the edit applier.

Mirrors `specs/018-dotnet-codegen/contracts/edit-operation.schema.json`. Validation is
hand-rolled rather than delegated to `jsonschema` so the runtime carries no extra dependency;
a drift guard in the contract test asserts this module and the schema agree on every payload.

Two rules live here that JSON Schema cannot express, and both are cost controls:
lazy placeholder content is rejected outright, and a rewrite that changes nothing is rejected
as a no-op (wasted output tokens, and an invitation to "tidy" unrelated code).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

AnchorKind = Literal["symbol", "text"]
Disposition = Literal["replace", "insert-into-type", "delete", "create-file"]

ANCHOR_KINDS: Final[frozenset[str]] = frozenset({"symbol", "text"})
DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {"replace", "insert-into-type", "delete", "create-file"}
)
ALLOWED_KEYS: Final[frozenset[str]] = frozenset(
    {"file", "anchor_kind", "symbol", "search", "disposition", "content", "reason"}
)
REQUIRED_KEYS: Final[tuple[str, ...]] = ("file", "anchor_kind", "disposition")

# Lazy-output signatures. Each requires an ellipsis or an explicit "unchanged" claim, so a
# legitimate comment is not mistaken for a truncated member.
_LAZY_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\.\.\.\s*(?:the\s+)?(?:rest|existing|unchanged|remaining)", re.IGNORECASE),
    re.compile(
        r"(?:rest|remainder)\s+of\s+(?:the\s+)?"
        r"(?:method|class|file|code|implementation|body)\s+(?:is\s+)?unchanged",
        re.IGNORECASE,
    ),
    re.compile(r"//\s*\.\.\.", re.IGNORECASE),
    re.compile(r"/\*\s*\.\.\.", re.IGNORECASE),
    re.compile(r"existing\s+code\s+(?:here|unchanged|omitted)", re.IGNORECASE),
)

_WHITESPACE = re.compile(r"\s+")


class EditOperationError(ValueError):
    """Raised when a payload violates the EditOperation contract."""


@dataclass(frozen=True)
class EditOperation:
    """One content-anchored modification to one file. Position is never part of the contract."""

    file: str
    anchor_kind: AnchorKind
    disposition: Disposition
    symbol: str | None = None
    search: str | None = None
    content: str | None = None
    reason: str | None = None

    @property
    def anchor(self) -> str:
        """The anchor value, whichever kind this operation uses."""
        value = self.symbol if self.anchor_kind == "symbol" else self.search
        assert value is not None  # guaranteed by parse_operation
        return value


def _reject_unknown_and_missing(payload: dict) -> None:
    unknown = sorted(set(payload) - ALLOWED_KEYS)
    if unknown:
        raise EditOperationError(f"unknown field(s): {', '.join(unknown)}")

    missing = [key for key in REQUIRED_KEYS if key not in payload]
    if missing:
        raise EditOperationError(f"missing required field(s): {', '.join(missing)}")


def _reject_bad_enums(anchor_kind: object, disposition: object) -> None:
    if anchor_kind not in ANCHOR_KINDS:
        raise EditOperationError(
            f"anchor_kind must be one of {sorted(ANCHOR_KINDS)}, got {anchor_kind!r}"
        )
    if disposition not in DISPOSITIONS:
        raise EditOperationError(
            f"disposition must be one of {sorted(DISPOSITIONS)}, got {disposition!r}"
        )


def _reject_bad_anchor(payload: dict, anchor_kind: str) -> None:
    required, forbidden = ("symbol", "search") if anchor_kind == "symbol" else ("search", "symbol")
    if not payload.get(required):
        raise EditOperationError(f"anchor_kind {anchor_kind!r} requires a non-empty {required!r}")
    if forbidden in payload:
        raise EditOperationError(
            f"anchor_kind {anchor_kind!r} must not carry {forbidden!r} - anchors are exclusive"
        )


def _reject_bad_content(payload: dict, disposition: str) -> None:
    has_content = "content" in payload
    if disposition == "delete":
        if has_content:
            raise EditOperationError("disposition 'delete' must not carry content")
        return
    if not has_content:
        raise EditOperationError(f"disposition {disposition!r} requires content")
    if not isinstance(payload["content"], str) or not payload["content"].strip():
        raise EditOperationError("content must be a non-empty string")


def _reject_lazy_content(content: str) -> None:
    for pattern in _LAZY_PATTERNS:
        match = pattern.search(content)
        if match is not None:
            raise EditOperationError(
                f"content is a lazy placeholder ({match.group(0)!r}); emit the complete member"
            )


def _reject_noop(content: str, existing_text: str) -> None:
    if _WHITESPACE.sub(" ", content).strip() == _WHITESPACE.sub(" ", existing_text).strip():
        raise EditOperationError("content is identical to the existing text - no-op rewrite")


def parse_operation(payload: dict, existing_text: str | None = None) -> EditOperation:
    """Validate a wire payload and return the operation, or raise `EditOperationError`.

    `existing_text` is the current text at the anchor, when known. Supplying it enables the
    no-op check; omitting it simply skips that rule.
    """
    if not isinstance(payload, dict):
        raise EditOperationError(f"payload must be an object, got {type(payload).__name__}")

    _reject_unknown_and_missing(payload)
    anchor_kind = payload["anchor_kind"]
    disposition = payload["disposition"]
    _reject_bad_enums(anchor_kind, disposition)

    if not isinstance(payload["file"], str) or not payload["file"].strip():
        raise EditOperationError("file must be a non-empty string")

    _reject_bad_anchor(payload, anchor_kind)
    _reject_bad_content(payload, disposition)

    content = payload.get("content")
    if content is not None:
        _reject_lazy_content(content)
        if existing_text is not None:
            _reject_noop(content, existing_text)

    return EditOperation(
        file=payload["file"],
        anchor_kind=anchor_kind,
        disposition=disposition,
        symbol=payload.get("symbol"),
        search=payload.get("search"),
        content=content,
        reason=payload.get("reason"),
    )
