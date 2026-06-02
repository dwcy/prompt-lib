# -*- coding: utf-8 -*-
"""Smoke + regression tests for LocalScreen.

Regression target: `GITIGNORE_BY_TEMPLATE` was referenced in `views/local.py`
without being imported, crashing with `NameError` when the gitignore checkbox
was toggled with a template selected.
"""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Checkbox, Select

from cabal.views.local import LocalScreen


class _Host(App):
    """Minimal host App that pushes LocalScreen at mount."""

    def on_mount(self) -> None:
        self.push_screen(LocalScreen())


def test_local_screen_module_imports_gitignore_constant() -> None:
    """Direct regression: the constant must resolve in local.py's namespace."""
    from cabal.views import local as local_mod

    assert hasattr(local_mod, "GITIGNORE_BY_TEMPLATE")
    assert "python" in local_mod.GITIGNORE_BY_TEMPLATE


@pytest.mark.asyncio
async def test_local_screen_mounts() -> None:
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, LocalScreen)


@pytest.mark.asyncio
async def test_local_screen_gitignore_toggle_with_template_does_not_crash() -> None:
    """Reproduces the original NameError path.

    Steps that crashed before the fix:
      1. Mount LocalScreen.
      2. Pick a template from the Select dropdown (sets `_template_path()`).
      3. Tick the gitignore checkbox — `_refresh()` runs the
         `picked.stem not in GITIGNORE_BY_TEMPLATE` branch.
    """
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, LocalScreen)

        select = screen.query_one("#loc-tpl-select", Select)
        first_value = next(v for _, v in screen.template_options)
        select.value = first_value
        await pilot.pause()

        gitignore_cb = screen.query_one("#loc-gitignore", Checkbox)
        gitignore_cb.value = True
        await pilot.pause()


@pytest.mark.asyncio
async def test_local_screen_each_checkbox_toggle_does_not_crash() -> None:
    """Broader regression: every action-checkbox should be safe to toggle."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        for cb_id in ("loc-scaffold", "loc-template", "loc-gitignore", "loc-git", "loc-speckit"):
            cb = screen.query_one(f"#{cb_id}", Checkbox)
            cb.value = not cb.value
            await pilot.pause()
