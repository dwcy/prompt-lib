"""Unit tests for ``agents.pr_review`` prompt-builder + NO_REVIEW sentinel (T017).

These are fine-grained unit tests for two helpers that ``PrReviewAgent`` uses
internally; the contract test (T015) covers the consumer-side end-to-end flow.

Implementation guidance for T019
--------------------------------

These tests assume the module exposes two pure helpers alongside the
``PrReviewAgent`` class::

    from orchestrator.agents.pr_review import build_prompt, detect_no_review

    def build_prompt(trigger_event: TriggerEvent, diff_text: str) -> str: ...
    def detect_no_review(text: str) -> tuple[bool, str | None]: ...

Contract for ``build_prompt``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Returns the prompt template documented in
``specs/002-agent-orchestrator/contracts/a2a-delegation.contract.md``. The
prompt MUST contain the repo slug, ``#<pr_number>``, the PR URL, the
``headRefName`` and ``baseRefName`` branch names, and the author login. The
``diff_text`` is embedded inside a triple-backtick fenced block.

The trigger-event payload is the source of truth for the title, URL, branch
names and author — the test constructs a ``TriggerEvent`` whose ``payload``
carries those keys. (The architect is free to pick the exact payload key
names; this test does not pin them — it asserts on the rendered prompt
content.)

Contract for ``detect_no_review``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Returns ``(True, "<reason>")`` only when the entire stripped response is a
single line beginning with ``NO_REVIEW:``. The reason is the substring after
the colon, stripped. Mid-paragraph occurrences (e.g. an example in a longer
review body) MUST NOT trigger a skip.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from orchestrator.agents.pr_review import build_prompt, detect_no_review
from orchestrator.triggers.base import TriggerEvent

REPO = "owner/repo"
PR_NUMBER = 42
HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"
PR_URL = "https://github.com/owner/repo/pull/42"


def _trigger_event() -> TriggerEvent:
    return TriggerEvent(
        kind="pr.opened",
        repo=REPO,
        pr_number=PR_NUMBER,
        head_sha=HEAD_SHA,
        detected_at=datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC),
        payload={
            "title": "Add the thing",
            "url": PR_URL,
            "headRefName": "feature/the-thing",
            "baseRefName": "main",
            "author_login": "octocat",
        },
    )


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_prompt_contains_repo_pr_number_url_branch_author(self) -> None:
        diff = "diff --git a/x b/x\n+added\n"

        prompt = build_prompt(_trigger_event(), diff)

        assert REPO in prompt
        assert "#42" in prompt
        assert PR_URL in prompt
        assert "feature/the-thing" in prompt
        assert "main" in prompt
        assert "octocat" in prompt

    def test_prompt_embeds_diff_in_fenced_block(self) -> None:
        diff = "diff --git a/x b/x\n+added line\n-removed line\n"

        prompt = build_prompt(_trigger_event(), diff)

        # Triple-backtick fenced block somewhere in the prompt that wraps the
        # diff text. We allow an optional language tag after the opening fence.
        pattern = re.compile(
            r"```[A-Za-z0-9_-]*\n"
            + re.escape(diff)
            + r"```",
            re.DOTALL,
        )
        assert pattern.search(prompt) is not None


# ---------------------------------------------------------------------------
# detect_no_review
# ---------------------------------------------------------------------------


class TestDetectNoReview:
    def test_no_review_sentinel_detection_strips_prefix_and_keeps_reason(self) -> None:
        skipped, reason = detect_no_review("NO_REVIEW: binary diff")

        assert skipped is True
        assert reason == "binary diff"

    def test_no_review_sentinel_only_at_line_start(self) -> None:
        body = (
            "Looks good overall. One nit: avoid swallowing exceptions, e.g. "
            "NO_REVIEW: would be a misleading variable name."
        )

        skipped, reason = detect_no_review(body)

        assert skipped is False
        assert reason is None
