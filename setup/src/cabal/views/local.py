# -*- coding: utf-8 -*-
"""LocalScreen — extracted from setup/src/cabal/wizard.py for feature 005."""

from __future__ import annotations

import filecmp
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from rich.markup import escape as escape_markup
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container, Horizontal, ScrollableContainer, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button, Checkbox, DataTable, Footer, Header, Input, Label,
    MarkdownViewer, OptionList, RadioButton, RadioSet, Rule, Select, Static,
)
from textual.widgets.option_list import Option
from textual.widget import Widget

from cabal._paths import GLOBAL_DIR, TARGET, REPO_DIR, ENV_DIR, ENV_FILE, RESOURCE_ROOT
from cabal.app_widgets import AppHeader
from cabal.banner import HexBanner, render_banner
from cabal.components import COMPONENTS, Component, ENV_DESCRIPTIONS, FileStatus
from cabal.diff_apply import (
    apply_statuses,
    backup_settings,
    diff_component,
    find_extras,
    prune_backups,
)
from cabal.env_detect import detect_env, find_env_vars
from cabal.env_summary import render_env_summary
from cabal.git_config import apply_git_line_endings, recommended_autocrlf
from cabal.gitignore_presets import GITIGNORE_BY_TEMPLATE
from cabal.installers.gh import gh_device_init, gh_device_poll, gh_fetch_token
from cabal.mcp_ops import (
    claude_mcp_add_from_template,
    claude_mcp_remove,
    enumerate_mcp_servers,
)
from cabal.tools import (
    ENV_INSTALLERS,
    ENV_TOOL_GROUPS,
    TOOLS,
    Tool,
    VERSION_FLOORS,
    WINGET_IDS,
    _below_floor,
    _installer_for,
    _outdated_packages,
    _probe_key,
)
from cabal.updates import check_for_updates, do_git_pull
from cabal.widgets.env_panel import EnvPanel
from cabal.widgets.update_panel import UpdatePanel

class LocalScreen(Screen):
    """Set up .claude/ in another project."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
    ]

    def __init__(self) -> None:
        super().__init__()
        tpls = sorted((GLOBAL_DIR / "project-templates").glob("*.md")) if (GLOBAL_DIR / "project-templates").exists() else []
        self.template_options = [(p.stem, str(p)) for p in tpls]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Local project setup ✦[/bold bright_magenta]\n"
                "[dim]Pick a project folder and the actions to take.[/dim]",
                classes="panel",
            )
            with Horizontal():
                yield Label("Project path: ")
                yield Button("Browse…", id="loc-browse")
                yield Input(value=str(Path.cwd()), id="loc-path")
            yield Checkbox("Create .claude/ scaffolding (skills/, hooks/, settings.local.json)", value=True, id="loc-scaffold")
            yield Static(
                "Creates .claude/skills/, .claude/hooks/, and settings.local.json with an empty permissions stub.\n"
                "Claude Code discovers project-local agents and skills from these dirs at session start (docs/architecture.md).\n"
                "[yellow]⚑ TODO: Edit .claude/settings.local.json → add allow[] entries for commands this project needs "
                "(e.g. npm, pytest, dotnet). Run Initialize env vars from the home screen first if MCP servers are needed.[/yellow]\n"
                "Test: ls .claude/ → skills/, hooks/, settings.local.json all present.",
                classes="help-text",
            )
            yield Checkbox("Apply CLAUDE.md project template", value=False, id="loc-template")
            yield Static(
                "Copies a starter CLAUDE.md from global/project-templates/ into the project root.\n"
                "Sets project conventions and stack hints that Claude reads at every session start (docs/rules-output-styles.md).\n"
                "Test: open a new Claude Code session in the project — the SessionStart hook detects CLAUDE.md and invokes @load-project.\n"
                "Review and customise the generated CLAUDE.md before committing it.",
                classes="help-text",
            )
            if self.template_options:
                yield Select(self.template_options, id="loc-tpl-select", prompt="Pick template…")
            yield Checkbox(
                "Add .gitignore matching the project template",
                value=False, id="loc-gitignore",
            )
            yield Static(
                "Writes a stack-specific .gitignore using the template picked above "
                "(python / dotnet / frontend / monorepo / unity / other).\n"
                "If a .gitignore already exists, the new entries are appended (with a header comment) instead of overwriting.\n"
                "Test: cat .gitignore → see the additions; `git status` should immediately ignore build dirs.",
                classes="help-text",
            )
            yield Checkbox("Apply git repo-init template (hooks + .editorconfig + .gitattributes)", value=False, id="loc-git")
            yield Static(
                "Copies global/git/.editorconfig and .gitattributes to the project root, and hook scripts to .git/hooks/.\n"
                "Requires git init to have been run in the project first.\n"
                "[yellow]⚑ TODO (Unix): run chmod +x .git/hooks/* after apply — Windows copies do not preserve execute bit.[/yellow]\n"
                "Test: ls .git/hooks/ → hook files present. Open a commit to confirm hooks fire.",
                classes="help-text",
            )
            yield Checkbox("Initialize Spec Kit (specify init --here --integration claude)", value=False, id="loc-speckit")
            yield Static(
                "Runs `specify init --here --integration claude` in the project to scaffold the Spec Kit workflow "
                "(.specify/, slash commands like /speckit-specify, /speckit-plan, /speckit-tasks).\n"
                "Requires the `specify` CLI — install it from the Tools screen (or run `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git`).\n"
                "If the target directory already contains .specify/, this passes `--force` to merge.\n"
                "Test: ls .specify/ → templates, scripts, memory all present. Open Claude Code → /speckit-specify should be listed.",
                classes="help-text",
            )
            yield Static("")
            yield DataTable(id="loc-preview", show_cursor=False)
            yield Static("")
            with Horizontal():
                yield Button("Refresh preview", id="loc-refresh")
                yield Button("Apply (Ctrl+A)", id="loc-apply", variant="success")
                yield Button("Back (Esc)", id="loc-back")
            yield Static("", id="loc-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#loc-preview", DataTable)
        tbl.add_columns("Action", "Path", "State")
        self._refresh()

    def _project(self) -> Path:
        return Path(self.query_one("#loc-path", Input).value).expanduser()

    def _selected(self) -> dict:
        return {
            "scaffold":  self.query_one("#loc-scaffold", Checkbox).value,
            "template":  self.query_one("#loc-template", Checkbox).value,
            "gitignore": self.query_one("#loc-gitignore", Checkbox).value,
            "git":       self.query_one("#loc-git", Checkbox).value,
            "speckit":   self.query_one("#loc-speckit", Checkbox).value,
        }

    def _template_path(self) -> Path | None:
        if not self.template_options:
            return None
        try:
            sel = self.query_one("#loc-tpl-select", Select)
        except Exception:
            return None
        if not isinstance(sel.value, str):
            return None
        return Path(sel.value)

    def _open_browser(self) -> None:
        from cabal.views.folder_browser import FolderBrowserScreen
        raw = self.query_one("#loc-path", Input).value
        start = Path(raw).expanduser()
        if not start.is_dir():
            start = Path.cwd()
        def _cb(path: Path | None) -> None:
            if path is not None:
                self.query_one("#loc-path", Input).value = str(path)
                self._refresh()
        self.app.push_screen(FolderBrowserScreen(start), _cb)

    def _refresh(self) -> None:
        tbl = self.query_one("#loc-preview", DataTable)
        tbl.clear()
        project = self._project()
        sel = self._selected()
        tpl = self._template_path() if sel["template"] else None

        if not project.exists() or not project.is_dir():
            tbl.add_row("[red]Path not a directory[/red]", str(project), "[red]ERROR[/red]")
            return

        if sel["scaffold"]:
            for sub in [".claude", ".claude/skills", ".claude/hooks"]:
                p = project / sub
                state = "[dim]exists (kept)[/dim]" if p.exists() else "[green]NEW[/green]"
                tbl.add_row("scaffold", sub + "/", state)
            sl = project / ".claude" / "settings.local.json"
            tbl.add_row("scaffold", ".claude/settings.local.json", "[dim]exists (kept)[/dim]" if sl.exists() else "[green]NEW[/green]")

        if sel["template"]:
            if tpl:
                target = project / "CLAUDE.md"
                state = "[yellow]EXISTS — would OVERWRITE[/yellow]" if target.exists() else "[green]NEW[/green]"
                tbl.add_row("template", f"CLAUDE.md  (from {tpl.stem})", state)
            else:
                tbl.add_row("template", "—", "[yellow]Pick a template above[/yellow]")

        if sel["gitignore"]:
            picked = self._template_path()
            if picked is None:
                tbl.add_row("gitignore", ".gitignore", "[yellow]Pick a template above[/yellow]")
            elif picked.stem not in GITIGNORE_BY_TEMPLATE:
                tbl.add_row("gitignore", ".gitignore", f"[yellow]no preset for '{picked.stem}'[/yellow]")
            else:
                target = project / ".gitignore"
                state = "[yellow]EXISTS — will APPEND[/yellow]" if target.exists() else "[green]NEW[/green]"
                tbl.add_row("gitignore", f".gitignore  ({picked.stem} preset)", state)

        if sel["git"]:
            git_src = GLOBAL_DIR / "git"
            git_dir = project / ".git"
            if not git_dir.exists():
                tbl.add_row("git_init", ".git/", "[yellow]will run git init[/yellow]")
            if not git_src.exists():
                tbl.add_row("git_init", "global/git/ in repo", "[red]MISSING[/red]")
            else:
                hooks_src = git_src / "hooks"
                if hooks_src.exists():
                    for f in sorted(hooks_src.iterdir()):
                        if f.is_file():
                            target = git_dir / "hooks" / f.name
                            state = "[yellow]EXISTS — would OVERWRITE[/yellow]" if git_dir.exists() and target.exists() else "[green]NEW[/green]"
                            tbl.add_row("git_init", f".git/hooks/{f.name}", state)
                for f in sorted(git_src.iterdir()):
                    if f.is_file():
                        target = project / f.name
                        state = "[yellow]EXISTS — would OVERWRITE[/yellow]" if target.exists() else "[green]NEW[/green]"
                        tbl.add_row("git_init", f.name, state)

        if sel["speckit"]:
            if not shutil.which("specify"):
                tbl.add_row("speckit", "specify CLI", "[red]not installed — see Tools screen[/red]")
            else:
                specify_dir = project / ".specify"
                if specify_dir.exists():
                    tbl.add_row("speckit", ".specify/", "[yellow]EXISTS — will run with --force[/yellow]")
                else:
                    tbl.add_row("speckit", ".specify/", "[green]NEW (specify init --here --integration claude)[/green]")

    def action_apply(self) -> None:
        project = self._project()
        if not project.is_dir():
            self.query_one("#loc-status", Static).update(f"[red]Not a directory:[/red] {project}")
            return
        sel = self._selected()
        msgs = []

        if sel["scaffold"]:
            (project / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
            (project / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
            sl = project / ".claude" / "settings.local.json"
            if not sl.exists():
                sl.write_text('{\n  "permissions": {\n    "allow": []\n  }\n}\n', encoding="utf-8")
            msgs.append(
                "[green]✓ Created .claude/ scaffold[/green]\n"
                "  Verify: ls .claude/ → skills/, hooks/, settings.local.json\n"
                "  [yellow]⚑ TODO: edit .claude/settings.local.json — add allow[] entries for this project's commands.[/yellow]"
            )

        if sel["template"]:
            tpl = self._template_path()
            if tpl:
                shutil.copy2(tpl, project / "CLAUDE.md")
                msgs.append(
                    f"[green]✓ Wrote CLAUDE.md from {tpl.stem}[/green]\n"
                    "  Verify: open a new Claude Code session here — SessionStart hook should invoke @load-project.\n"
                    "  Review CLAUDE.md and customise stack conventions before committing."
                )
            else:
                msgs.append("[yellow]Skipped template — none picked[/yellow]")

        if sel["gitignore"]:
            picked = self._template_path()
            if picked is None:
                msgs.append("[yellow]Skipped .gitignore — no template selected[/yellow]")
            else:
                ignore_text = GITIGNORE_BY_TEMPLATE.get(picked.stem)
                if not ignore_text:
                    msgs.append(f"[yellow]Skipped .gitignore — no preset for '{picked.stem}'[/yellow]")
                else:
                    target = project / ".gitignore"
                    header = f"# Added by cabal wizard ({picked.stem} preset)\n"
                    if target.exists():
                        existing = target.read_text(encoding="utf-8")
                        combined = existing.rstrip() + "\n\n" + header + ignore_text
                        target.write_text(combined, encoding="utf-8")
                        msgs.append(
                            f"[green]✓ Appended .gitignore ({picked.stem} preset)[/green]\n"
                            f"  Verify: cat .gitignore → new {picked.stem} block at the bottom.\n"
                            "  Review for overlap with existing entries before committing."
                        )
                    else:
                        target.write_text(header + ignore_text, encoding="utf-8")
                        msgs.append(
                            f"[green]✓ Wrote .gitignore ({picked.stem} preset)[/green]\n"
                            "  Verify: cat .gitignore → stack-specific ignore rules present.\n"
                            "  `git status` should immediately ignore build/cache dirs."
                        )

        if sel["git"]:
            git_src = GLOBAL_DIR / "git"
            git_dir = project / ".git"
            if not git_dir.exists():
                if not shutil.which("git"):
                    msgs.append("[red]✗ git not found on PATH — cannot run git init[/red]")
                else:
                    r = subprocess.run(["git", "init", str(project)], capture_output=True, text=True)
                    if r.returncode == 0:
                        msgs.append("[green]✓ git init[/green]")
                    else:
                        msgs.append(f"[red]✗ git init failed:[/red] {r.stderr.strip()}")
            if git_dir.exists() and git_src.exists():
                hooks_src = git_src / "hooks"
                if hooks_src.exists():
                    hd = git_dir / "hooks"
                    hd.mkdir(parents=True, exist_ok=True)
                    for f in hooks_src.iterdir():
                        if f.is_file():
                            shutil.copy2(f, hd / f.name)
                for f in git_src.iterdir():
                    if f.is_file():
                        shutil.copy2(f, project / f.name)
                msgs.append(
                    "[green]✓ Applied git repo-init template[/green]\n"
                    "  Verify: ls .git/hooks/ → hook scripts present.\n"
                    "  [yellow]⚑ TODO (Unix only): chmod +x .git/hooks/* — execute bit not preserved on Windows copy.[/yellow]"
                )
            elif not git_src.exists():
                msgs.append("[yellow]Skipped git_init — template missing in repo[/yellow]")

        if sel["speckit"]:
            if not shutil.which("specify"):
                msgs.append(
                    "[red]✗ specify CLI not on PATH[/red] — install it from the Tools screen "
                    "(or `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git`), "
                    "then re-run."
                )
            else:
                cmd = [
                    "specify", "init", "--here",
                    "--integration", "claude",
                    "--ignore-agent-tools",
                ]
                if (project / ".specify").exists():
                    cmd.append("--force")
                with self.app.suspend():
                    r = subprocess.run(cmd, cwd=str(project))
                if r.returncode == 0:
                    msgs.append(
                        f"[green]✓ Spec Kit initialized[/green]  [dim]({' '.join(cmd)})[/dim]\n"
                        "  Verify: ls .specify/ → templates/, scripts/, memory/ present.\n"
                        "  In Claude Code, /speckit-specify, /speckit-plan, /speckit-tasks should be available."
                    )
                else:
                    msgs.append(f"[red]✗ specify init failed (exit {r.returncode})[/red]")

        self.query_one("#loc-status", Static).update("\n".join(msgs))
        self._refresh()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refresh()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._refresh()

    def on_select_changed(self, event: Select.Changed) -> None:
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "loc-back":
            self.app.pop_screen()
        elif bid == "loc-browse":
            self._open_browser()
        elif bid == "loc-refresh":
            self._refresh()
        elif bid == "loc-apply":
            self.action_apply()


