# -*- coding: utf-8 -*-
"""Start view (ProjectGateScreen) footer — no init/open shortcuts, palette hidden."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from textual.color import Color
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button
from textual.widgets import DataTable
from textual.widgets import Footer
from textual.widgets import Static

from cabal import gh_accounts
from cabal.app import CabalApp
from cabal.recent_projects import RecentProject
from cabal.views.gh_accounts_modal import GhAccountsModal
from cabal.views.project_gate import ProjectGateScreen, _fmt_time
from cabal.widgets.env_panel import EnvPanel
from cabal.widgets.update_panel import UpdatePanel


def test_gate_bindings_are_quit_only():
    keys = {b.key for b in ProjectGateScreen.BINDINGS}

    assert keys == {"ctrl+q"}


def test_gate_last_opened_uses_relative_time_until_week_old():
    now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)

    assert _fmt_time((now - timedelta(seconds=30)).isoformat(), now) == "just now"
    assert _fmt_time((now - timedelta(minutes=1)).isoformat(), now) == "1 minute ago"
    assert _fmt_time((now - timedelta(minutes=42)).isoformat(), now) == "42 minutes ago"
    assert _fmt_time((now - timedelta(hours=1)).isoformat(), now) == "1 hour ago"
    assert _fmt_time((now - timedelta(hours=6)).isoformat(), now) == "6 hours ago"
    assert _fmt_time((now - timedelta(days=1)).isoformat(), now) == "1 day ago"
    assert _fmt_time((now - timedelta(days=7)).isoformat(), now) == "7 days ago"
    assert _fmt_time((now - timedelta(days=8)).isoformat(), now) == "2026-06-16"


@pytest.mark.asyncio
async def test_gate_command_palette_hidden_from_footer():
    app = CabalApp()

    async with app.run_test(size=(120, 80)) as pilot:
        await pilot.pause()

        assert app.screen.query_one(Footer).show_command_palette is False


@pytest.mark.asyncio
async def test_gate_github_button_opens_accounts_modal(monkeypatch):
    monkeypatch.setattr(gh_accounts, "list_accounts", lambda host="github.com": [])
    monkeypatch.setattr(EnvPanel, "refresh_env", lambda self: None)
    monkeypatch.setattr(UpdatePanel, "on_mount", lambda self: None)
    app = CabalApp()

    async with app.run_test(size=(120, 80)) as pilot:
        await pilot.pause()
        await pilot.pause()

        app.screen.query_one("#btn-github", Button).press()
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, GhAccountsModal)
        assert str(app.screen.query_one("#gha-add", Button).label) == "Login to GitHub"


@pytest.mark.asyncio
async def test_github_account_change_refreshes_overview(monkeypatch):
    refreshed: list[str | None] = []

    def fake_refresh_env(self: EnvPanel) -> None:
        refreshed.append(self.id)

    monkeypatch.setattr(EnvPanel, "refresh_env", fake_refresh_env)
    monkeypatch.setattr(UpdatePanel, "on_mount", lambda self: None)
    app = CabalApp()

    async with app.run_test(size=(120, 80)) as pilot:
        await pilot.pause()
        refreshed.clear()

        app._after_github_accounts_closed(True)

        assert refreshed == ["env-summary"]
        assert app.env_needs_refresh is False


@pytest.mark.asyncio
async def test_current_setup_panel_places_version_metadata_above_os(monkeypatch):
    from cabal.widgets import update_panel

    update_result = {
        "status": "up_to_date",
        "hash": "abc1234",
        "date": "2026-06-24",
    }
    monkeypatch.setattr(update_panel, "check_for_updates", lambda: update_result)
    monkeypatch.setattr(
        update_panel.widget_cache,
        "load_entry",
        lambda key: update_result if key == "updates" else None,
    )
    monkeypatch.setattr(update_panel.widget_cache, "save_entry", lambda *_: None)
    app = CabalApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        outer = app.screen.query_one("#env-summary")
        info = app.screen.query_one("#env-info")
        version_row = app.screen.query_one("#env-version-row")
        version_meta = app.screen.query_one("#env-version-meta", Static)
        system_row = app.screen.query_one("#env-row-system")
        env_paths = app.screen.query_one("#env-paths", Static)
        tools_row = app.screen.query_one("#env-tools-row")
        update_panel = app.screen.query_one(UpdatePanel)
        update_msg = app.screen.query_one("#update-msg", Static)
        refresh = app.screen.query_one("#env-refresh", Static)
        github_button = app.screen.query_one("#btn-github", Button)
        github_green = Color.parse("#16A34A")
        github_green_light = Color.parse("#86EFAC")
        github_green_dark = Color.parse("#166534")
        dark_pink = Color.parse("#CC006B")
        version_text = str(version_meta.content)
        assert not outer.styles.border
        assert outer.styles.background.a == 0
        assert outer.styles.padding.top == 0
        assert outer.styles.padding.right == 0
        assert outer.styles.padding.bottom == 0
        assert outer.styles.padding.left == 0
        assert update_msg.display is False
        assert "\n" not in version_text
        assert "[bold #5FAFFF]Cabal:[/]" in version_text
        assert "Latest version" in version_text
        assert "[bold #55FFA5]✓ Latest version" in version_text
        assert "hash:" in version_text
        assert "[bold #5FAFFF]hash:[/]" in version_text
        assert "[bold #FF85B3]abc1234" in version_text
        assert "date:" in version_text
        assert "[bold #5FAFFF]date:[/]" in version_text
        assert "[bold #FF85B3]2026-06-24" in version_text
        assert "Overview" in info.border_title
        assert "Local setup" not in info.border_title
        assert "Current setup" not in info.border_title
        assert "README" in info.border_subtitle
        assert "screen.readme" in info.border_subtitle
        assert info.styles.border.top[1] == dark_pink
        assert info.styles.border.right[1] == dark_pink
        assert info.styles.border.bottom[1] == dark_pink
        assert info.styles.border.left[1] == dark_pink
        assert version_row.parent is info
        assert version_meta.parent is version_row
        assert update_panel.parent is version_row
        assert refresh.parent.parent is update_panel
        assert system_row.parent is info
        assert info.children.index(version_row) + 1 == info.children.index(system_row)
        refresh.display = True
        refresh.update("[cyan]X[/] [dim italic]refreshing...[/]")
        update_panel.sync_visibility()
        await pilot.pause()
        version_row_region = app.screen.find_widget(version_row).region
        version_meta_region = app.screen.find_widget(version_meta).region
        refresh_region = app.screen.find_widget(refresh).region
        assert version_meta_region.width > 1
        assert refresh_region.right == version_row_region.right
        assert env_paths.parent is info
        assert tools_row.parent is info
        assert info.children.index(env_paths) + 1 == info.children.index(tools_row)
        system_row_region = app.screen.find_widget(system_row).region
        system_first_cell_region = app.screen.find_widget(system_row.children[0]).region
        env_paths_region = app.screen.find_widget(env_paths).region
        assert system_row_region.x == version_meta_region.x == env_paths_region.x
        assert system_first_cell_region.x == env_paths_region.x
        assert github_button.styles.background == github_green
        assert github_button.styles.border.top[1] == github_green_light
        assert github_button.styles.border.bottom[1] == github_green_dark


def test_current_setup_update_available_metadata_uses_remote_hash():
    text = EnvPanel._format_update_metadata(
        {
            "status": "behind",
            "remote": "def5678",
            "behind_count": 2,
        }
    )

    assert "Update available (2)" in text
    assert "\n" not in text
    assert "[bold #5FAFFF]Cabal:[/]" in text
    assert "hash:" in text
    assert "[bold #5FAFFF]hash:[/]" in text
    assert "def5678" in text
    assert "date:" in text
    assert "[bold #5FAFFF]date:[/]" in text


@pytest.mark.asyncio
async def test_gate_project_actions_and_recents_are_framed_in_panels():
    app = CabalApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        select_panel = app.screen.query_one("#gate-select-panel")
        description = app.screen.query_one("#gate-project-description", Static)
        recents_panel = app.screen.query_one("#gate-recents-panel")
        recents_table = app.screen.query_one("#gate-recents", DataTable)
        actions = app.screen.query_one("#gate-actions")
        clone_button = app.screen.query_one("#gate-clone", Button)

        assert "Projects" in select_panel.border_title
        with pytest.raises(NoMatches):
            app.screen.query_one("#gate-select-copy", Static)
        assert "Create, clone, or open projects" in str(description.content)
        assert "agents, skills, hooks, and settings" in str(description.content)
        assert description.parent is select_panel
        assert actions.parent is select_panel
        assert select_panel.children.index(description) + 1 == select_panel.children.index(actions)
        assert app.screen.query_one("#gate-init", Button).parent.parent is select_panel
        assert clone_button.parent.parent is select_panel
        assert app.screen.query_one("#gate-open", Button).parent.parent is select_panel
        assert recents_panel.parent is select_panel
        assert recents_table.parent is recents_panel
        assert len(recents_table.columns) == 3
        assert [str(column.label) for column in recents_table.ordered_columns] == [
            "Project",
            "Path",
            "Last opened",
        ]
        assert str(recents_table.styles.width) == "1fr"
        assert recents_table.styles.margin.left == 0
        assert recents_table.styles.margin.right == 0
        assert "Recent Projects" in recents_panel.border_title
        github_green = Color.parse("#16A34A")
        github_green_light = Color.parse("#86EFAC")
        github_green_dark = Color.parse("#166534")
        assert "-primary" not in clone_button.classes
        assert clone_button.styles.background == github_green
        assert clone_button.styles.border.top[1] == github_green_light
        assert clone_button.styles.border.bottom[1] == github_green_dark


@pytest.mark.asyncio
async def test_gate_starts_at_top_even_with_recent_projects(monkeypatch):
    from cabal.views import project_gate

    monkeypatch.setattr(
        project_gate,
        "load_recents",
        lambda: [
            RecentProject(
                path=f"C:/projects/example-{idx}",
                name=f"example-{idx}",
                action="open",
                last_opened="2026-06-24T07:00:00+00:00",
            )
            for idx in range(12)
        ],
    )
    app = CabalApp()

    async with app.run_test(size=(80, 12)) as pilot:
        await pilot.pause()
        await pilot.pause()

        assert app.focused is app.screen.query_one("#gate-init", Button)
        assert app.screen.query_one("#gate-scroll", VerticalScroll).scroll_y == 0


@pytest.mark.asyncio
async def test_gate_recents_table_columns_fill_available_width(monkeypatch):
    from cabal.views import project_gate

    monkeypatch.setattr(
        project_gate,
        "load_recents",
        lambda: [
            RecentProject(
                path="C:/x",
                name="x",
                action="open",
                last_opened="2026-06-24T07:00:00+00:00",
            )
        ],
    )
    app = CabalApp()

    async with app.run_test(size=(120, 80)) as pilot:
        await pilot.pause()
        await pilot.pause()

        table = app.screen.query_one("#gate-recents", DataTable)
        columns = list(table.ordered_columns)
        render_width = sum(column.get_render_width(table) for column in columns)

        assert table.content_region.width > 0
        assert render_width == table.content_region.width
        assert table.virtual_size.width == table.content_region.width
        assert columns[1].width > len("C:/x")
