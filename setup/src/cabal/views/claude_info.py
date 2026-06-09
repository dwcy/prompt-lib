# -*- coding: utf-8 -*-
"""ClaudeInfoScreen — modal reference: models, what's new, tips, and useful commands."""

from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, MarkdownViewer, Static

from cabal._paths import GLOBAL_DIR, TARGET
from cabal.app_widgets import AppHeader
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


class ClaudeInfoScreen(Screen):
    """Scrollable reference for models, recent features, tips and commands."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        try:
            md = build_claude_info_markdown()
        except Exception as e:
            yield Static(f"[red]Could not build Claude info: {e}[/red]")
            yield Footer(show_command_palette=False)
            return
        yield MarkdownViewer(md, show_table_of_contents=True)
        yield Footer(show_command_palette=False)
