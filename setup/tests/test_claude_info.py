# -*- coding: utf-8 -*-
"""Claude Info screen changelog disclosure and service-health rendering."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button, Collapsible

from cabal.claude_release_feed import (
    ChangelogItem,
    ChangelogRelease,
    ClaudeServiceStatus,
    StatusIncident,
)
from cabal.views.claude_info import (
    ChangelogReleaseCard,
    ClaudeInfoScreen,
    release_additions_markdown,
    release_other_changes_markdown,
    service_status_markup,
)


def _release(version: str = "2.1.211") -> ChangelogRelease:
    return ChangelogRelease(
        version=version,
        date="July 11, 2026",
        changes=(
            ChangelogItem("Added", "Added nested-agent stream output"),
            ChangelogItem("Fixed", "Fixed permission previews"),
            ChangelogItem("Improved", "Improved startup performance"),
        ),
    )


def test_release_markdown_keeps_added_separate_from_other_categories() -> None:
    release = _release()

    added = release_additions_markdown(release)
    other = release_other_changes_markdown(release)

    assert "nested-agent stream output" in added
    assert "permission previews" not in added
    assert "### Fixed" in other
    assert "### Improved" in other


def test_service_status_markup_marks_partial_outage_as_degraded() -> None:
    status = ClaudeServiceStatus(
        component_status="partial_outage",
        overall_indicator="minor",
        overall_description="Minor Service Outage",
        updated_at="2026-07-16T19:49:13.185Z",
        incidents=(StatusIncident("Elevated errors", "identified", "major"),),
    )

    markup, css_class = service_status_markup(status)

    assert css_class == "status-degraded"
    assert "Claude Code: Partial Outage" in markup
    assert "Elevated errors" in markup


@pytest.mark.asyncio
async def test_changelog_cards_show_added_and_collapse_other_changes(monkeypatch) -> None:
    monkeypatch.setattr(ClaudeInfoScreen, "on_mount", lambda self: None)
    app = App()

    async with app.run_test() as pilot:
        screen = ClaudeInfoScreen()
        await app.push_screen(screen)
        screen._replace_releases((_release(),))
        await pilot.pause()

        card = screen.query_one(ChangelogReleaseCard)
        disclosure = card.query_one(Collapsible)

        assert disclosure.collapsed is True
        assert screen.query_one("#ci-load-more", Button).display is False


@pytest.mark.asyncio
async def test_changelog_load_more_batches_versions(monkeypatch) -> None:
    monkeypatch.setattr(ClaudeInfoScreen, "on_mount", lambda self: None)
    app = App()
    releases = tuple(_release(f"2.1.{number}") for number in range(30, 17, -1))

    async with app.run_test() as pilot:
        screen = ClaudeInfoScreen()
        await app.push_screen(screen)
        screen._replace_releases(releases)
        await pilot.pause()

        assert len(screen.query(ChangelogReleaseCard)) == screen.BATCH_SIZE
        assert screen.query_one("#ci-load-more", Button).display is True

        screen._show_next_batch()
        await pilot.pause()

        assert len(screen.query(ChangelogReleaseCard)) == len(releases)
        assert screen.query_one("#ci-load-more", Button).display is False
