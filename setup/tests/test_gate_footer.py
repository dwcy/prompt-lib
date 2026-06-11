# -*- coding: utf-8 -*-
"""Start view (ProjectGateScreen) footer — no init/open shortcuts, palette hidden."""

from __future__ import annotations

import pytest
from textual.widgets import Footer

from cabal.app import CabalApp
from cabal.views.project_gate import ProjectGateScreen


def test_gate_bindings_are_quit_only():
    keys = {b.key for b in ProjectGateScreen.BINDINGS}

    assert keys == {"ctrl+q"}


@pytest.mark.asyncio
async def test_gate_command_palette_hidden_from_footer():
    app = CabalApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.query_one(Footer).show_command_palette is False
