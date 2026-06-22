from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from cabal.views.knowledge import KnowledgeScreen
from cabal.widgets.okf_panel import OkfPanel


class _KnowledgeHost(App):
    def compose(self) -> ComposeResult:
        yield KnowledgeScreen()


class _PanelHost(App):
    def compose(self) -> ComposeResult:
        yield OkfPanel()


@pytest.mark.asyncio
async def test_knowledge_screen_mounts() -> None:
    app = _KnowledgeHost()
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.query_one("#okf-status", Static)
        help_text = str(app.query_one("#okf-export-help", Static).render())
        assert "docs/okf/prompt-lib" in help_text
        assert "auto-inject" in help_text


@pytest.mark.asyncio
async def test_okf_panel_mounts() -> None:
    app = _PanelHost()
    async with app.run_test() as pilot:
        await pilot.pause()

        assert "OKF" in str(app.query_one("#okf-panel-body", Static).render())
