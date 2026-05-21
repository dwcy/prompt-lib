"""Unit tests for ``orchestrator.triggers.base`` (T010).

Pins the ``TriggerEvent`` validation rules and the ``Trigger`` Protocol shape
documented in ``data-model.md`` § "Entity: TriggerEvent" and ``research.md``
R5. Per Constitution Principle III these tests land BEFORE the implementation
(T011); until then every test is expected to fail with ``ImportError`` on
``orchestrator.triggers.base``.

Implementation guidance for T011: mark the ``Trigger`` Protocol with
``@typing.runtime_checkable`` so ``isinstance`` works against trivially
conforming classes — this test file relies on that.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

VALID_HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"


def _import_base():
    from orchestrator.triggers import base

    return base


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "kind": "pr.opened",
        "repo": "owner/repo",
        "pr_number": 1,
        "head_sha": VALID_HEAD_SHA,
        "detected_at": datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestTriggerEventConstruction:
    def test_valid_kwargs_accepted(self) -> None:
        base = _import_base()

        event = base.TriggerEvent(**_valid_kwargs())

        assert event.kind == "pr.opened"
        assert event.repo == "owner/repo"
        assert event.pr_number == 1
        assert event.head_sha == VALID_HEAD_SHA

    def test_payload_defaults_to_empty_dict(self) -> None:
        base = _import_base()
        kwargs = _valid_kwargs()
        kwargs.pop("payload", None)

        event = base.TriggerEvent(**kwargs)

        assert event.payload == {}

    def test_payload_accepts_arbitrary_dict(self) -> None:
        base = _import_base()

        event = base.TriggerEvent(**_valid_kwargs(payload={"raw": {"a": 1}}))

        assert event.payload == {"raw": {"a": 1}}


# ---------------------------------------------------------------------------
# kind enum
# ---------------------------------------------------------------------------


class TestKindValidation:
    @pytest.mark.parametrize("valid_kind", ["pr.opened", "pr.updated", "issue.opened"])
    def test_valid_kinds_accepted(self, valid_kind: str) -> None:
        base = _import_base()

        event = base.TriggerEvent(**_valid_kwargs(kind=valid_kind))

        assert event.kind == valid_kind

    @pytest.mark.parametrize(
        "invalid_kind",
        ["pr.closed", "", "PR.OPENED", "pr_opened"],
    )
    def test_invalid_kinds_rejected(self, invalid_kind: str) -> None:
        base = _import_base()

        with pytest.raises(ValidationError):
            base.TriggerEvent(**_valid_kwargs(kind=invalid_kind))


class TestIssueEventKind:
    """issue.opened kind accepts sentinel head_sha and stores issue_number."""

    def test_issue_opened_with_sentinel_sha_accepted(self) -> None:
        base = _import_base()

        event = base.TriggerEvent(
            kind="issue.opened",
            repo="owner/repo",
            pr_number=99,
            head_sha="0" * 40,
            detected_at=datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC),
            payload={
                "issue_number": 99,
                "title": "Something broken",
                "body": "details",
                "labels": ["bug"],
                "author": "alice",
            },
        )

        assert event.kind == "issue.opened"
        assert event.pr_number == 99
        assert event.payload["issue_number"] == 99

    def test_issue_event_payload_arbitrary_fields(self) -> None:
        base = _import_base()

        event = base.TriggerEvent(
            kind="issue.opened",
            repo="owner/repo",
            pr_number=1,
            head_sha="0" * 40,
            detected_at=datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC),
            payload={"issue_number": 1, "title": "t", "body": "", "labels": [], "author": "u"},
        )

        assert event.payload["labels"] == []
        assert event.payload["body"] == ""


# ---------------------------------------------------------------------------
# repo slug
# ---------------------------------------------------------------------------


class TestRepoValidation:
    @pytest.mark.parametrize(
        "invalid_repo",
        ["foo", "foo//bar", "/foo/bar", "", "foo bar/baz"],
    )
    def test_invalid_repo_rejected(self, invalid_repo: str) -> None:
        base = _import_base()

        with pytest.raises(ValidationError):
            base.TriggerEvent(**_valid_kwargs(repo=invalid_repo))

    @pytest.mark.parametrize(
        "valid_repo",
        ["owner/repo", "foo-bar/baz_qux.dot", "a/b"],
    )
    def test_valid_repo_accepted(self, valid_repo: str) -> None:
        base = _import_base()

        event = base.TriggerEvent(**_valid_kwargs(repo=valid_repo))

        assert event.repo == valid_repo


# ---------------------------------------------------------------------------
# pr_number
# ---------------------------------------------------------------------------


class TestPrNumberValidation:
    @pytest.mark.parametrize("invalid_pr", [0, -1, -100])
    def test_non_positive_pr_number_rejected(self, invalid_pr: int) -> None:
        base = _import_base()

        with pytest.raises(ValidationError):
            base.TriggerEvent(**_valid_kwargs(pr_number=invalid_pr))

    def test_positive_pr_number_accepted(self) -> None:
        base = _import_base()

        event = base.TriggerEvent(**_valid_kwargs(pr_number=42))

        assert event.pr_number == 42


# ---------------------------------------------------------------------------
# head_sha
# ---------------------------------------------------------------------------


class TestHeadShaValidation:
    @pytest.mark.parametrize(
        "invalid_sha",
        [
            "0123456789ABCDEF0123456789ABCDEF01234567",
            "0123456789abcdef0123456789abcdef0123",
            "0123456789abcdef0123456789abcdef0123456789",
            "0123456789abcdef0123456789abcdef0123456g",
            "",
            "not-a-sha",
        ],
    )
    def test_invalid_head_sha_rejected(self, invalid_sha: str) -> None:
        base = _import_base()

        with pytest.raises(ValidationError):
            base.TriggerEvent(**_valid_kwargs(head_sha=invalid_sha))

    def test_valid_head_sha_accepted(self) -> None:
        base = _import_base()

        event = base.TriggerEvent(**_valid_kwargs(head_sha="a" * 40))

        assert event.head_sha == "a" * 40


# ---------------------------------------------------------------------------
# detected_at
# ---------------------------------------------------------------------------


class TestDetectedAtSerialization:
    def test_serializes_to_iso_8601_utc(self) -> None:
        base = _import_base()

        event = base.TriggerEvent(**_valid_kwargs())
        dumped = json.loads(event.model_dump_json())

        detected_at = dumped["detected_at"]
        assert detected_at.endswith("Z") or detected_at.endswith("+00:00")
        assert "2026-05-10T12:00:00" in detected_at


# ---------------------------------------------------------------------------
# Frozen + extra='forbid'
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_event_is_frozen(self) -> None:
        base = _import_base()
        event = base.TriggerEvent(**_valid_kwargs())

        with pytest.raises(ValidationError):
            event.pr_number = 999  # type: ignore[misc]

    def test_unknown_kwargs_rejected(self) -> None:
        base = _import_base()

        with pytest.raises(ValidationError):
            base.TriggerEvent(**_valid_kwargs(unknown_field="oops"))


# ---------------------------------------------------------------------------
# Trigger Protocol
# ---------------------------------------------------------------------------


class _ConformingTrigger:
    async def events(self) -> AsyncIterator[object]:
        if False:
            yield  # pragma: no cover

    async def aclose(self) -> None:
        return None


class TestTriggerProtocol:
    def test_conforming_class_passes_isinstance_check(self) -> None:
        base = _import_base()

        instance = _ConformingTrigger()

        assert isinstance(instance, base.Trigger)
