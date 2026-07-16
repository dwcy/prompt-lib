# -*- coding: utf-8 -*-
"""ClaudeInfoScreen — modal reference: models, what's new, tips, and useful commands."""

from __future__ import annotations

import json
import webbrowser
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from rich.markup import escape as escape_markup
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Markdown,
    MarkdownViewer,
    Static,
    TabbedContent,
    TabPane,
)

from cabal._paths import GLOBAL_DIR, TARGET
from cabal.app_widgets import AppHeader
from cabal.claude_release_feed import (
    CHANGELOG_URL,
    STATUS_URL,
    ChangelogItem,
    ChangelogRelease,
    ClaudeServiceStatus,
    get_cached_changelog,
    get_cached_status,
    refresh_changelog,
    refresh_status,
)
from cabal.widgets.claude_stats_panel import read_claude_account_state

_ALIAS_FRIENDLY = {"opus": "Opus 4.8", "sonnet": "Sonnet 4.6", "haiku": "Haiku 4.5"}

_MODEL_LINEUP = [
    (
        "Opus 4.8",
        "claude-opus-4-8",
        "Most capable — deep reasoning, large refactors, long agentic runs. "
        "Has a 1M-context variant and a Fast mode (`/fast`).",
    ),
    (
        "Sonnet 4.6",
        "claude-sonnet-4-6",
        "Balanced speed and quality — a strong default for everyday coding.",
    ),
    (
        "Haiku 4.5",
        "claude-haiku-4-5",
        "Fastest and cheapest — quick edits and high-volume or latency-sensitive tasks.",
    ),
]


def read_configured_model() -> str | None:
    """The `model` value from the deployed settings.json, falling back to the repo source."""
    for base in (TARGET, GLOBAL_DIR):
        p = base / "settings.json"
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        model = (data or {}).get("model")
        if model:
            return str(model)
    return None


def _models_section(configured: str | None) -> str:
    lines = ["## Models", ""]
    if configured:
        friendly = _ALIAS_FRIENDLY.get(configured.lower())
        shown = f"`{configured}`" + (f" ({friendly})" if friendly else "")
        lines.append(
            f"**Your configured model:** {shown} — change it any time with `/model`."
        )
    else:
        lines.append("**Your configured model:** _not set_ — pick one with `/model`.")
    lines += [
        "",
        "The current Claude 4.x family used by Claude Code:",
        "",
        "| Model | ID | Best for |",
        "| --- | --- | --- |",
    ]
    for name, model_id, blurb in _MODEL_LINEUP:
        lines.append(f"| **{name}** | `{model_id}` | {blurb} |")
    lines += [
        "",
        "_Actual model access depends on your Claude plan. Run `/status` in the "
        "interactive `claude` UI to see your plan, usage and active model._",
    ]
    return "\n".join(lines)


_WHATS_NEW = """\
## What's new & changed

- **Skills** — reusable `/<skill>` slash commands with their own instructions and tools.
  Add one as `~/.claude/skills/<name>.md`.
- **Subagents & orchestration** — delegate work to specialist `@agents` that run with
  their own context; dispatch several in parallel for full-stack tasks.
- **Plan mode** — research a change and get an approved plan before any edits are made.
- **Output styles** — switch the response format/persona per session.
- **Statusline** — a custom status line at the bottom of the CLI (`/statusline`).
- **Fast mode** — `/fast` keeps Opus quality with faster output on Opus 4.6+.
- **MCP servers** — connect external tools/data sources; manage them with `/mcp`.
- **Hooks** — run scripts on session start, before/after tools, and on stop.
"""

_TIPS = """\
## Tips & tricks

- Prefix a line with `!` to run a shell command inline and feed its output to Claude.
- Prefix with `#` to save a memory that persists across sessions.
- Reference files with `@path/to/file`; paste or drag images straight into the prompt.
- `/clear` wipes the conversation; `/compact` summarises it to reclaim context.
- `/resume` reopens a previous conversation.
- Be specific about the *done condition* — Claude verifies against what you describe.
"""

_COMMANDS = """\
## Useful commands

`/help` · `/model` · `/clear` · `/compact` · `/resume` · `/config` · `/status`
· `/cost` · `/mcp` · `/agents` · `/init` · `/login` · `/doctor` · `/fast`

Run `/help` inside `claude` for the authoritative, up-to-date list.
"""


def build_claude_info_markdown() -> str:
    st = read_claude_account_state()
    header = ["# ✦ Claude info", ""]
    if st.email:
        header.append(f"**Signed in:** {st.email}")
    else:
        header.append("**Signed in:** _not signed in — run_ `claude /login`")
    sections = [
        "\n".join(header),
        _models_section(read_configured_model()),
        _WHATS_NEW,
        _TIPS,
        _COMMANDS,
    ]
    return "\n\n".join(sections)


_OTHER_CATEGORY_ORDER = (
    "Fixed",
    "Improved",
    "Changed",
    "Updated",
    "Restored",
    "Removed",
    "Deprecated",
    "Other",
)


def _change_list_markdown(items: tuple[ChangelogItem, ...]) -> str:
    return "\n".join(f"- {item.text}" for item in items)


def release_additions_markdown(release: ChangelogRelease) -> str:
    if release.additions:
        return "### Added\n\n" + _change_list_markdown(release.additions)
    return "### Added\n\n_No entries labeled Added in this release._"


def release_other_changes_markdown(release: ChangelogRelease) -> str:
    grouped: dict[str, list[ChangelogItem]] = defaultdict(list)
    for item in release.other_changes:
        grouped[item.category].append(item)

    sections: list[str] = []
    ordered_categories = list(_OTHER_CATEGORY_ORDER)
    ordered_categories.extend(
        sorted(category for category in grouped if category not in ordered_categories)
    )
    for category in ordered_categories:
        items = grouped.get(category)
        if not items:
            continue
        sections.append(f"### {category}\n\n{_change_list_markdown(tuple(items))}")
    return "\n\n".join(sections)


class ChangelogReleaseCard(Widget):
    """One release: additions are visible; all other categories are disclosed."""

    def __init__(self, release: ChangelogRelease) -> None:
        super().__init__()
        self.release = release

    def compose(self) -> ComposeResult:
        date = f"  [dim]{escape_markup(self.release.date)}[/dim]" if self.release.date else ""
        yield Static(
            f"[bold bright_magenta]{escape_markup(self.release.version)}[/bold bright_magenta]{date}",
            classes="ci-release-title",
        )
        yield Markdown(
            release_additions_markdown(self.release),
            classes="ci-release-added",
        )
        if self.release.other_changes:
            count = len(self.release.other_changes)
            with Collapsible(
                title=f"Fixed, improved & other changes ({count})",
                collapsed=True,
                classes="ci-release-other",
            ):
                yield Markdown(release_other_changes_markdown(self.release))


def service_status_markup(status: ClaudeServiceStatus) -> tuple[str, str]:
    component_label = status.component_status.replace("_", " ").title()
    css_class = {
        "operational": "status-operational",
        "degraded_performance": "status-degraded",
        "partial_outage": "status-degraded",
        "major_outage": "status-outage",
        "under_maintenance": "status-maintenance",
    }.get(status.component_status, "status-unknown")
    rich_style = {
        "status-operational": "bold #55FFA5",
        "status-degraded": "bold yellow",
        "status-outage": "bold red",
        "status-maintenance": "bold cyan",
        "status-unknown": "bold dim",
    }[css_class]
    lines = [
        f"[{rich_style}]● Claude Code: {escape_markup(component_label)}[/]",
        f"[dim]Overall: {escape_markup(status.overall_description)}[/dim]",
    ]
    if status.incidents:
        incident = status.incidents[0]
        state = incident.status.replace("_", " ")
        lines.append(
            f"[yellow]{escape_markup(incident.name)}"
            f" ({escape_markup(state)})[/yellow]"
        )
    return "\n".join(lines), css_class


class ClaudeInfoScreen(Screen):
    """Live Claude Code changelog, service health, and local reference."""

    BATCH_SIZE = 12

    DEFAULT_CSS = """
    ClaudeInfoScreen #ci-status-row {
        height: auto;
        min-height: 4;
        margin: 1 2 0 2;
        padding: 0 1;
        border: round #CC006B;
        background: $boost;
    }
    ClaudeInfoScreen #ci-service-status {
        width: 1fr;
        height: auto;
        padding: 0 1;
        content-align: left middle;
    }
    ClaudeInfoScreen #ci-status-row Button {
        min-width: 13;
        margin: 0 0 0 1;
    }
    ClaudeInfoScreen #ci-tabs { height: 1fr; }
    ClaudeInfoScreen #ci-feed-header {
        height: auto;
        padding: 1 2 0 2;
        margin: 0;
    }
    ClaudeInfoScreen #ci-feed-heading {
        width: 1fr;
        height: auto;
        content-align: left middle;
    }
    ClaudeInfoScreen #ci-feed-note {
        height: auto;
        margin: 0 2 1 2;
        color: $text-muted;
    }
    ClaudeInfoScreen #ci-changelog-scroll { padding: 0 2 1 2; }
    ClaudeInfoScreen #ci-releases { height: auto; }
    ClaudeInfoScreen #ci-load-more {
        width: 24;
        margin: 1 0;
    }
    ClaudeInfoScreen .status-operational { color: #55FFA5; }
    ClaudeInfoScreen .status-degraded { color: yellow; }
    ClaudeInfoScreen .status-outage { color: red; }
    ClaudeInfoScreen .status-maintenance { color: cyan; }
    ClaudeInfoScreen .status-unknown { color: $text-muted; }
    ChangelogReleaseCard {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1 1 1;
        border-bottom: solid $primary-darken-2;
    }
    ChangelogReleaseCard .ci-release-title {
        height: auto;
        padding: 1 0 0 0;
    }
    ChangelogReleaseCard .ci-release-added { height: auto; }
    ChangelogReleaseCard .ci-release-other {
        height: auto;
        margin: 0;
    }
    ChangelogReleaseCard Collapsible Markdown { height: auto; }
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._releases: tuple[ChangelogRelease, ...] = ()
        self._shown_release_count = 0

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Horizontal(id="ci-status-row"):
            yield Static(
                "[dim]Checking Claude service status…[/dim]",
                id="ci-service-status",
            )
            yield Button("Refresh", id="ci-refresh")
            yield Button("Open status ↗", id="ci-open-status", variant="primary")
        with TabbedContent(initial="ci-changelog-tab", id="ci-tabs"):
            with TabPane("Changelog", id="ci-changelog-tab"):
                with VerticalScroll(id="ci-changelog-scroll"):
                    with Horizontal(id="ci-feed-header"):
                        yield Static(
                            "[bold]Claude Code changelog[/bold]",
                            id="ci-feed-heading",
                        )
                        yield Button(
                            "Open source ↗",
                            id="ci-open-changelog",
                            variant="default",
                        )
                    yield Static(
                        "Fetching release notes…",
                        id="ci-feed-note",
                    )
                    yield Vertical(id="ci-releases")
                    yield Button("Load more versions", id="ci-load-more")
            with TabPane("Reference", id="ci-reference-tab"):
                try:
                    markdown = build_claude_info_markdown()
                except Exception as error:
                    markdown = f"# Claude info\n\nCould not build local reference: {error}"
                yield MarkdownViewer(markdown, show_table_of_contents=True)
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self.query_one("#ci-load-more", Button).display = False
        if cached_releases := get_cached_changelog():
            self._replace_releases(cached_releases)
            self.query_one("#ci-feed-note", Static).update(
                "Showing cached release notes while checking the source. "
                "Added entries stay visible; expand each disclosure for fixes and other changes."
            )
        if cached_status := get_cached_status():
            self._apply_status(cached_status)
        self._start_refresh()

    def action_refresh(self) -> None:
        self._start_refresh(force=True)

    def _start_refresh(self, *, force: bool = False) -> None:
        self.query_one("#ci-refresh", Button).disabled = True
        self.run_worker(
            lambda: self._refresh_remote(force=force),
            thread=True,
            exclusive=True,
            group="claude-info-refresh",
        )

    def _refresh_remote(self, *, force: bool) -> None:
        with ThreadPoolExecutor(max_workers=2) as pool:
            changelog_future = pool.submit(refresh_changelog, force=force)
            status_future = pool.submit(refresh_status, force=force)
            releases = changelog_future.result()
            status = status_future.result()
        try:
            self.app.call_from_thread(self._apply_remote, releases, status)
        except Exception:
            pass

    def _apply_remote(
        self,
        releases: tuple[ChangelogRelease, ...] | None,
        status: ClaudeServiceStatus | None,
    ) -> None:
        self.query_one("#ci-refresh", Button).disabled = False
        if releases:
            self._replace_releases(releases)
            self.query_one("#ci-feed-note", Static).update(
                f"{len(releases)} versions available from the official changelog. "
                "Added entries stay visible; expand each disclosure for fixes and other changes."
            )
        elif not self._releases:
            self.query_one("#ci-feed-note", Static).update(
                "[yellow]Could not fetch the Claude Code changelog. Press R to retry.[/yellow]"
            )
        if status is not None:
            self._apply_status(status)
        elif get_cached_status() is None:
            status_widget = self.query_one("#ci-service-status", Static)
            status_widget.set_classes("status-unknown")
            status_widget.update(
                "[yellow]● Claude Code status unavailable[/yellow]\n"
                "[dim]Open status.claude.com for live details.[/dim]"
            )

    def _apply_status(self, status: ClaudeServiceStatus) -> None:
        markup, css_class = service_status_markup(status)
        status_widget = self.query_one("#ci-service-status", Static)
        status_widget.set_classes(css_class)
        status_widget.update(markup)

    def _replace_releases(self, releases: tuple[ChangelogRelease, ...]) -> None:
        if releases == self._releases:
            return
        container = self.query_one("#ci-releases", Vertical)
        container.remove_children()
        self._releases = releases
        self._shown_release_count = 0
        self._show_next_batch()

    def _show_next_batch(self) -> None:
        start = self._shown_release_count
        end = min(start + self.BATCH_SIZE, len(self._releases))
        if end > start:
            cards = [ChangelogReleaseCard(release) for release in self._releases[start:end]]
            self.query_one("#ci-releases", Vertical).mount(*cards)
            self._shown_release_count = end
        button = self.query_one("#ci-load-more", Button)
        remaining = len(self._releases) - self._shown_release_count
        button.display = remaining > 0
        if remaining > 0:
            button.label = f"Load more versions ({remaining})"

    def _open_url(self, url: str) -> None:
        try:
            webbrowser.open(url)
        except Exception as error:
            self.notify(
                f"Could not open {url}: {error}",
                title="Open link",
                severity="error",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "ci-refresh":
            self.action_refresh()
        elif button_id == "ci-open-status":
            self._open_url(STATUS_URL)
        elif button_id == "ci-open-changelog":
            self._open_url(CHANGELOG_URL)
        elif button_id == "ci-load-more":
            self._show_next_batch()
