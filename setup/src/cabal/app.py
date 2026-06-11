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

from textual.app import App
from textual.binding import Binding

from cabal.clipboard import read_clipboard
from cabal.app_widgets import AppCommandsProvider, AppHeader  # noqa: F401  (re-export)
from cabal.views.claude_info import ClaudeInfoScreen  # noqa: F401
from cabal.views.env import EnvScreen  # noqa: F401
from cabal.views.folder_browser import FolderBrowserScreen  # noqa: F401
from cabal.views.gh_device import GhDeviceFlowScreen  # noqa: F401
from cabal.views.git_config import GitConfigScreen  # noqa: F401
from cabal.views.github_repos import GitHubReposScreen  # noqa: F401
from cabal.views.global_env import GlobalEnvScreen  # noqa: F401
from cabal.views.home import HomeScreen  # noqa: F401
from cabal.views.init_project import InitProjectScreen  # noqa: F401
from cabal.views.init_project_prompt import build_init_prompt, write_init_prompt  # noqa: F401
from cabal.views.local import LocalScreen  # noqa: F401
from cabal.views.mcp import McpScreen  # noqa: F401
from cabal.views.operations import OperationsScreen  # noqa: F401
from cabal.views.project_gate import ProjectGateScreen
from cabal.views.project_mcp import ProjectMcpScreen  # noqa: F401
from cabal.views.readme import ReadmeScreen  # noqa: F401
from cabal.views.restore import RestoreScreen  # noqa: F401
from cabal.views.statusline import StatuslineScreen  # noqa: F401
from cabal.views.tools import ToolsScreen  # noqa: F401
from cabal.views.update import UpdateScreen  # noqa: F401


class CabalApp(App):
    """CABAL — Agent Orchestration Setup."""

    selected_project: Path | None = None
    # Set by ToolsScreen after a successful install/update so HomeScreen re-scans
    # the "Current setup" panel on resume instead of showing stale tool state.
    env_needs_refresh: bool = False

    def project_path(self) -> Path:
        """The active project folder; falls back to cwd if somehow unset."""
        return self.selected_project or Path.cwd()

    @property
    def clipboard(self) -> str:
        """OS clipboard text, so ctrl+v pastes anything copied OS-wide.

        Textual's own `clipboard` only returns text copied inside the app; without
        this override `Input`/`TextArea` paste can't see an external copy. Falls back
        to the internal buffer when the OS clipboard is empty or unreadable.
        """
        return read_clipboard() or self._clipboard

    CSS = """
    Screen { background: $background; }

    .centered { content-align: center middle; }

    .panel {
        padding: 1 2;
        margin: 1 2;
        background: $panel;
        border: round $accent;
    }

    #banner {
        height: auto;
        padding: 1 2;
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
        color: cyan;
        text-style: italic;
    }
    #readme-link {
        width: auto;
        link-color: dodgerblue;
        link-style: underline;
        link-color-hover: $text;
        link-background-hover: dodgerblue;
    }

    #env-summary, #update-summary, #mcp-target {
        padding: 1 2;
        margin: 0 2;
        background: $boost;
        border: round $primary;
    }

    /* Every Horizontal needs explicit height or buttons collapse. */
    Horizontal {
        height: auto;
        align-vertical: middle;
        padding: 0 1;
        margin: 1 2;
    }
    /* UpdatePanel's row must sit flush with the Current setup panel's left
       edge; the broad Horizontal rule above would otherwise indent it. This
       id override outranks it (app CSS, id > type). */
    #update-row {
        margin: 0;
        padding: 0;
    }

    #home-bottom {
        height: 5;
        align-vertical: middle;
        padding: 0 2;
        margin: 0;
    }
    .home-spacer { width: 1fr; }

    .home-section {
        border: round $accent;
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
        border: double $accent;
        padding: 1 2;
        width: 72;
        height: 28;
    }
    #browser-path {
        height: 3;
        padding: 0 1;
        background: $boost;
        border: round $primary;
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
        Binding("left", "focus_previous", show=False),
        Binding("right", "focus_next", show=False),
    ]

    COMMANDS = {AppCommandsProvider}

    def on_mount(self) -> None:
        self.title = "CABAL"
        self.sub_title = "Agent Orchestration Setup"
        self.push_screen(ProjectGateScreen())


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
    except (ValueError, OSError):
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
