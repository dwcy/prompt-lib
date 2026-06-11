# -*- coding: utf-8 -*-
"""Smoke tests for FileViewerModal — diff-by-default for changed files, toggle to source."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import MarkdownViewer, Static

from cabal.widgets.file_viewer import FileViewerModal


@pytest.mark.asyncio
async def test_changed_file_opens_on_diff_and_toggles_to_source(tmp_path):
    deployed = tmp_path / "deployed.md"
    repo = tmp_path / "repo.md"
    deployed.write_text("line one\nline two\n", encoding="utf-8")
    repo.write_text("line one\nline two changed\nline three\n", encoding="utf-8")

    app = App()
    async with app.run_test() as pilot:
        modal = FileViewerModal(repo, "agents/foo.md", compare_path=deployed)
        await app.push_screen(modal)
        await pilot.pause()

        assert modal._diff_available is True
        assert isinstance(modal.query_one("#fv-body"), Static)

        await modal.action_toggle_diff()
        await pilot.pause()

        assert isinstance(modal.query_one("#fv-body"), MarkdownViewer)


@pytest.mark.asyncio
async def test_identical_content_has_no_diff(tmp_path):
    same = "x = 1\n"
    deployed = tmp_path / "deployed.py"
    repo = tmp_path / "repo.py"
    deployed.write_text(same, encoding="utf-8")
    repo.write_text(same, encoding="utf-8")

    app = App()
    async with app.run_test() as pilot:
        modal = FileViewerModal(repo, "statusline.py", compare_path=deployed)
        await app.push_screen(modal)
        await pilot.pause()

        assert modal._diff_available is False


@pytest.mark.asyncio
async def test_no_compare_path_shows_content_only(tmp_path):
    repo = tmp_path / "repo.md"
    repo.write_text("# Title\n", encoding="utf-8")

    app = App()
    async with app.run_test() as pilot:
        modal = FileViewerModal(repo, "plain")
        await app.push_screen(modal)
        await pilot.pause()

        assert modal._diff_available is False
        assert isinstance(modal.query_one("#fv-body"), MarkdownViewer)
