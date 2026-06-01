"""Smoke tests for LocalScreen (regression guard for the GITIGNORE_BY_TEMPLATE NameError).

LocalScreen._refresh() is triggered by checkbox changes; the previous bug only
surfaced when a user toggled the gitignore checkbox. The mount-and-refresh
smoke catches the import-shadow gap without depending on the user's actions.
"""

from __future__ import annotations

import pytest

from cabal.app import CabalApp
from cabal.views.local import LocalScreen


@pytest.mark.asyncio
async def test_local_screen_mounts_and_refresh_does_not_nameerror(tmp_project_dir):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = LocalScreen()
        app.push_screen(screen)
        await pilot.pause()

        screen._refresh()
        await pilot.pause()

        assert isinstance(app.screen, LocalScreen)


def test_gitignore_by_template_is_importable_in_local_module():
    from cabal.views import local as local_module

    assert isinstance(local_module.GITIGNORE_BY_TEMPLATE, dict)
    assert "python" in local_module.GITIGNORE_BY_TEMPLATE
