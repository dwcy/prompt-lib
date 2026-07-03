# -*- coding: utf-8 -*-
"""CabalApp — root Textual application + entry points.

`run()` is the public entry point used by `cabal.__main__:main`, the dev
shim (`setup/settings-configurator-ui.py`), and the PyInstaller exe.

`app.py` imports every screen at module top so PyInstaller's static
analyzer follows the graph and bundles them (per research.md R6).
"""

from __future__ import annotations

import signal
from pathlib import Path

from textual.actions import SkipAction
from textual.app import App
from textual.binding import Binding

from cabal.clipboard import read_clipboard, write_clipboard
from cabal.app_widgets import AppCommandsProvider, AppHeader  # noqa: F401  (re-export)
from cabal.views.claude_info import ClaudeInfoScreen  # noqa: F401
from cabal.views.model_assignments import ModelAssignmentsScreen  # noqa: F401
from cabal.views.clone_repo import CloneRepoScreen  # noqa: F401
from cabal.views.codex_conversion import CodexConversionScreen  # noqa: F401
from cabal.views.codex_local import CodexLocalScreen  # noqa: F401
from cabal.views.codex_update import CodexUpdateScreen  # noqa: F401
from cabal.views.env import EnvScreen  # noqa: F401
from cabal.views.folder_browser import FolderBrowserScreen  # noqa: F401
from cabal.views.gh_accounts_modal import GhAccountsModal  # noqa: F401
from cabal.views.gh_device import GhDeviceFlowScreen  # noqa: F401
from cabal.views.git_config import GitConfigScreen  # noqa: F401
from cabal.views.github_repos import GitHubReposScreen  # noqa: F401
from cabal.views.global_env import GlobalEnvScreen  # noqa: F401
from cabal.views.home import HomeScreen  # noqa: F401
from cabal.views.init_project import InitProjectScreen  # noqa: F401
from cabal.views.init_project_prompt import build_init_prompt, write_init_prompt  # noqa: F401
from cabal.views.knowledge import KnowledgeScreen  # noqa: F401
from cabal.views.local import LocalScreen  # noqa: F401
from cabal.views.mcp import McpScreen  # noqa: F401
from cabal.views.package_security import PackageSecurityScreen  # noqa: F401
from cabal.views.project_gate import ProjectGateScreen
from cabal.views.project_mcp import ProjectMcpScreen  # noqa: F401
from cabal.views.readme import ReadmeScreen  # noqa: F401
from cabal.views.restore import RestoreScreen  # noqa: F401
from cabal.views.sessions import SessionsScreen  # noqa: F401
from cabal.views.statusline import StatuslineScreen  # noqa: F401
from cabal.views.tools import ToolsScreen  # noqa: F401
from cabal.views.update import UpdateScreen  # noqa: F401


class CabalApp(App):
    """CABAL — agentic development configuration in one place."""

    ALLOW_SELECT = True

    selected_project: Path | None = None
    # Set by ToolsScreen after a successful install/update so HomeScreen re-scans
    # the "Local setup" panel on resume instead of showing stale tool state.
    env_needs_refresh: bool = False

    def project_path(self) -> Path:
        """The active project folder; falls back to cwd if somehow unset."""
        return self.selected_project or Path.cwd()

    def open_github_accounts(self) -> None:
        """Open gh account management and refresh local setup when it changes."""
        from cabal.views.gh_accounts_modal import GhAccountsModal

        self.push_screen(GhAccountsModal(), self._after_github_accounts_closed)

    def _after_github_accounts_closed(self, changed: bool | None) -> None:
        if not changed:
            return
        self.env_needs_refresh = True
        try:
            from cabal.widgets.env_panel import EnvPanel

            env_panel = self.screen.query_one("#env-summary", EnvPanel)
            self.env_needs_refresh = False
            env_panel.refresh_env()
        except Exception:
            pass
        try:
            dashboard = self.screen.query_one("#dashboard")
            dashboard.refresh_dashboard()
        except Exception:
            pass

    @property
    def clipboard(self) -> str:
        """OS clipboard text, so ctrl+v pastes anything copied OS-wide.

        Textual's own `clipboard` only returns text copied inside the app; without
        this override `Input`/`TextArea` paste can't see an external copy. Falls back
        to the internal buffer when the OS clipboard is empty or unreadable.
        """
        return read_clipboard() or self._clipboard

    def copy_to_clipboard(self, text: str) -> None:
        """Copy text to both Textual's buffer and the OS clipboard.

        Trailing whitespace per line is trimmed — Textual's cell-based text
        selection pads the copied region, and copying that padding is unwanted.
        """
        text = "\n".join(line.rstrip() for line in text.split("\n"))
        super().copy_to_clipboard(text)
        write_clipboard(text)

    CSS = """
    Screen { background: $background; }

    .centered { content-align: center middle; }

    .panel {
        padding: 1 2;
        margin: 1 2;
        background: $panel;
        border: round #CC006B;
    }

    #banner {
        height: auto;
        padding: 1 2 0 2;
        content-align: center middle;
    }

    #banner-row {
        height: auto;
        margin: 0 2;
        padding: 0;
        align-vertical: middle;
    }
    #subtitle {
        width: auto;
        color: #FF55A5;
        text-style: italic bold;
    }

    #env-summary {
        padding: 0;
        margin: 0 2;
        border: none;
    }

    #update-summary, #mcp-target {
        padding: 1 2;
        margin: 0 2;
        background: $boost;
        border: round #CC006B;
    }

    /* Every Horizontal needs explicit height or buttons collapse. */
    Horizontal {
        height: auto;
        align-vertical: middle;
        padding: 0 1;
        margin: 1 2;
    }
    /* UpdatePanel's row must sit flush with the Local setup panel's left
       edge; the broad Horizontal rule above would otherwise indent it. This
       id override outranks it (app CSS, id > type). */
    #update-row {
        margin: 0;
        padding: 0;
    }
    #env-version-row {
        margin: 0;
        padding: 0;
    }
    #env-row-system,
    #env-row-runtimes,
    #env-row-pkg-mgrs,
    #env-row-infra,
    #env-row-clis,
    #env-row-local-ai,
    #env-row-databases,
    #env-row-editors {
        margin: 1 0;
        padding: 0;
    }

    .home-section {
        border: round #CC006B;
        margin: 1 2;
        padding: 0 1 1 1;
        height: auto;
    }
    .home-section-title {
        color: $accent;
        padding: 0 1;
        height: 2;
        content-align: left middle;
    }
    .home-section-desc {
        padding: 0 1;
        margin: 0 0 1 0;
        height: auto;
        content-align: left top;
    }

    .ops-row {
        height: 5;
        align: center middle;
        margin: 0 1;
        padding: 0;
    }
    .ops-row Button { width: 1fr; }

    #home-nav, #ops-nav {
        height: 5;
        align: center middle;
    }
    #okf-actions {
        height: 5;
        align: center middle;
    }

    Button {
        margin: 0 1;
        min-width: 18;
        height: 3;
    }

    DataTable { height: auto; max-height: 25; margin: 0 2; }

    Input { margin: 0 1; height: 3; }

    /* Compact env-var rows: name | icon | input on one line */
    .env-row {
        height: 3;
        margin: 0 2;
        padding: 0;
        align-vertical: middle;
    }
    .env-name {
        width: 32;
        padding: 1 1 0 1;
        content-align: left middle;
    }
    .env-icon {
        width: 4;
        padding: 1 0 0 0;
        content-align: center middle;
    }
    .env-value { width: 1fr; }
    .env-browse { min-width: 10; width: 10; margin: 0; }

    Checkbox { margin: 0 2; height: auto; }

    .help-text {
        color: $text-muted;
        padding: 0 0 1 4;
        margin: 0 2;
        height: auto;
    }

    OptionList { max-height: 20; margin: 0 2; }

    RadioSet { margin: 0 1; height: auto; }

    Label { padding: 1 1 0 1; }

    MarkdownViewer { background: $background; }

    Footer { background: $primary-darken-1; }

    /* Folder browser modal */
    FolderBrowserScreen {
        align: center middle;
        background: $background 70%;
    }
    #browser-dialog {
        background: $panel;
        border: double #CC006B;
        padding: 1 2;
        width: 72;
        height: 28;
    }
    #browser-path {
        height: 3;
        padding: 0 1;
        background: $boost;
        border: round #CC006B;
        margin: 0 0 1 0;
        content-align: left middle;
    }
    #browser-list {
        height: 1fr;
        margin: 0;
    }
    #browser-actions {
        height: 3;
        margin: 1 0 0 0;
        padding: 0;
        align-horizontal: center;
    }
    #browser-actions Button { min-width: 16; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("q", "quit", "Quit", show=False),
        Binding("ctrl+c,ctrl+shift+c", "copy", "Copy", show=False),
        Binding("ctrl+v,ctrl+shift+v", "paste", "Paste", show=False),
        Binding("ctrl+shift+a", "select_all", "Select all", show=False),
        Binding("left", "focus_previous", show=False),
        Binding("right", "focus_next", show=False),
    ]

    COMMANDS = {AppCommandsProvider}

    def on_mount(self) -> None:
        self.title = "CABAL"
        self.sub_title = (
            "Cabal helps you manage your agentic development setup in one place."
        )
        self.push_screen(ProjectGateScreen())

    async def action_copy(self) -> None:
        """Copy selected text from the focused widget or active screen."""
        focused = self.focused
        if focused is not None and await self.run_action("copy", focused):
            return
        if await self.run_action("screen.copy_text"):
            return
        raise SkipAction()

    async def action_paste(self) -> None:
        """Paste clipboard text into the focused widget when it supports paste."""
        focused = self.focused
        if focused is not None and await self.run_action("paste", focused):
            return
        raise SkipAction()

    async def action_select_all(self) -> None:
        """Select all editable text, or all selectable text on the active screen."""
        focused = self.focused
        if focused is not None and await self.run_action("select_all", focused):
            return
        self.screen.text_select_all()


def _suppress_sigint() -> None:
    """Stop Ctrl+C from terminating the wizard, on every view.

    Textual already routes the ctrl+c *key* to native copy / a "press ctrl+q"
    hint — it never quits. The real killer is OS-level: on Windows a Ctrl+C
    pressed while a worker subprocess (winget / git / npm / env-detect) shares
    the console sends CTRL_C_EVENT to the whole process group, taking the parent
    down with it. Ignoring SIGINT keeps the app alive; Ctrl+C stays free for
    copy, and quit remains ctrl+q / q.
    """
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except ValueError, OSError:
        # Not the main thread, or a platform without SIGINT — non-fatal.
        pass


def main() -> None:
    _suppress_sigint()
    CabalApp().run()


def run() -> None:
    """Public entry point (alias for `main`). Used by cabal.__main__ and the dev shim."""
    main()


if __name__ == "__main__":
    main()
