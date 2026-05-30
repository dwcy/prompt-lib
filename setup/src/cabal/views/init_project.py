# -*- coding: utf-8 -*-
"""InitProjectScreen — scaffold a brand-new project from a GitHub or local template."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.coordinate import Coordinate
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, Footer, Input, Label, OptionList, RadioButton, RadioSet, Static,
)
from textual.widgets.option_list import Option

from cabal._paths import GLOBAL_DIR
from cabal.app_widgets import AppHeader
from cabal.claude_cli import ClaudeRunResult, spawn_claude
from cabal.gh_templates import GitHubTemplateRef, download_tarball, list_user_templates
from cabal.init_project_service import (
    ApplyReport, InjectableFile, LocalTemplateRef,
    apply_plan, count_project_mcp_entries, ensure_mcp_gitignored,
    enumerate_github_template_files, enumerate_local_template_files,
)
from cabal.views.init_project_prompt import build_init_prompt, write_init_prompt


_NAME_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
_SCAFFOLD_RELPATHS = [".claude/skills", ".claude/hooks", ".claude/agents", ".claude/settings.local.json"]


def _target_is_empty_or_only_mcp_json(target: Path) -> bool:
    if not target.exists():
        return True
    if not target.is_dir():
        return False
    entries = list(target.iterdir())
    if not entries:
        return True
    return len(entries) == 1 and entries[0].name == ".mcp.json"


class InitProjectScreen(Screen):
    """Scaffold a brand-new project from a template (GitHub or local)."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._gh_templates: list[GitHubTemplateRef] = []
        self._local_templates: list[LocalTemplateRef] = []
        self._injectables: list[InjectableFile] = []
        self._gh_extract_dir: Path | None = None
        self._mcp_entries_count: int = 0
        self._template_attribution: str = ""
        self._apply_in_progress: bool = False
        self._claude_proc: subprocess.Popen | None = None
        self._cancel_requested: bool = False

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Init new project ✦[/bold bright_magenta]\n"
                "[dim]Scaffold a brand-new project from a template. Pick a parent dir, name it, choose a template.[/dim]",
                classes="panel",
            )
            with Horizontal():
                yield Label("Parent dir:")
                yield Button("Browse…", id="init-browse")
                yield Input(value=str(Path.cwd()), id="init-parent")
            with Horizontal():
                yield Label("Project name:")
                yield Input(placeholder="my-new-project", id="init-name")
            yield Static("", id="init-name-status", classes="help-text")
            with Horizontal():
                yield Label("Template source:")
                with RadioSet(id="init-source"):
                    yield RadioButton("GitHub template repo", value=True, id="init-source-github")
                    yield RadioButton("Local template", id="init-source-local")
            yield OptionList(id="init-template-list")
            yield Static("", id="init-template-status", classes="help-text")
            yield Static("", id="init-mcp-summary", classes="help-text")
            with Horizontal():
                yield Button("[E] Edit Project MCP…", id="init-edit-mcp", disabled=True)
            yield DataTable(id="init-files", show_cursor=True, cursor_type="row", zebra_stripes=True)
            yield Static("", id="init-summary", classes="help-text")
            with Horizontal():
                yield Button("[A] Apply", id="init-apply", variant="success", disabled=True)
                yield Button("Cancel", id="init-cancel", variant="default")
                yield Button("Back (Esc)", id="init-back")
            yield Static("", id="init-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#init-files", DataTable)
        tbl.add_columns("✓", "Path", "Size", "Origin")
        tpl_dir = GLOBAL_DIR / "project-templates"
        tpls = sorted(tpl_dir.glob("*.md")) if tpl_dir.exists() else []
        self._local_templates = [
            LocalTemplateRef(stem=p.stem, path=p, gitignore_preset_name=p.stem) for p in tpls
        ]
        self.query_one("#init-template-status", Static).update(
            "[yellow]⏳ Fetching GitHub template repos…[/]"
        )
        self.run_worker(self._fetch_gh_templates, thread=True, exclusive=True)

    def _fetch_gh_templates(self) -> None:
        try:
            refs = list_user_templates()
        except Exception as e:
            self.app.call_from_thread(self._on_gh_error, str(e))
            return
        self.app.call_from_thread(self._on_gh_templates, refs)

    def _on_gh_templates(self, refs: list[GitHubTemplateRef]) -> None:
        self._gh_templates = refs
        if not refs:
            self.query_one("#init-source-github", RadioButton).disabled = True
            self.query_one("#init-source-local", RadioButton).value = True
            self.query_one("#init-template-status", Static).update(
                "[yellow]No GitHub template repos available — using local templates.[/]"
            )
            self._populate_local()
            return
        lst = self.query_one("#init-template-list", OptionList)
        lst.clear_options()
        for r in refs:
            label = f"{r.owner}/{r.name}  [dim]{r.description or ''}[/dim]"
            lst.add_option(Option(label, id=f"gh::{r.owner}/{r.name}"))
        self.query_one("#init-template-status", Static).update(
            f"[green]✓[/green] {len(refs)} GitHub template repos loaded"
        )

    def _on_gh_error(self, msg: str) -> None:
        self.query_one("#init-template-status", Static).update(
            f"[yellow]{msg} — falling back to local templates.[/yellow]"
        )
        self.query_one("#init-source-github", RadioButton).disabled = True
        self.query_one("#init-source-local", RadioButton).value = True
        self._populate_local()

    def _populate_local(self) -> None:
        lst = self.query_one("#init-template-list", OptionList)
        lst.clear_options()
        for ref in self._local_templates:
            lst.add_option(Option(f"{ref.stem}  [dim](local)[/dim]", id=f"local::{ref.stem}"))
        self.query_one("#init-template-status", Static).update(
            f"[dim]{len(self._local_templates)} local templates available[/dim]"
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id or ""
        if oid.startswith("gh::"):
            slug = oid[4:]
            ref = next((r for r in self._gh_templates if f"{r.owner}/{r.name}" == slug), None)
            if ref is not None:
                self._start_gh_download(ref)
        elif oid.startswith("local::"):
            stem = oid[7:]
            ref = next((r for r in self._local_templates if r.stem == stem), None)
            if ref is not None:
                self._stage_local(ref)

    def _start_gh_download(self, ref: GitHubTemplateRef) -> None:
        self.query_one("#init-files", DataTable).clear()
        self.query_one("#init-summary", Static).update("[yellow]⏳ Downloading template tarball…[/yellow]")

        def _run() -> None:
            try:
                d = download_tarball(ref)
                files = enumerate_github_template_files(d)
                self.app.call_from_thread(self._on_download_done, ref, d, files)
            except Exception as e:
                self.app.call_from_thread(self._on_download_error, str(e))

        self.run_worker(_run, thread=True, exclusive=True)

    def _on_download_done(self, ref: GitHubTemplateRef, extract_dir: Path, files: list[InjectableFile]) -> None:
        if self._gh_extract_dir and self._gh_extract_dir.exists():
            shutil.rmtree(self._gh_extract_dir, ignore_errors=True)
        self._gh_extract_dir = extract_dir
        self._injectables = files
        self._template_attribution = f"GitHub: {ref.owner}/{ref.name}@{ref.default_branch}"
        self._render_files_table()
        total_bytes = sum(f.size_bytes for f in files)
        self.query_one("#init-summary", Static).update(
            f"[green]✓[/green] {len(files)} files staged ({total_bytes / 1024:.1f} KB)"
        )
        self._refresh_apply_state()

    def _on_download_error(self, msg: str) -> None:
        self.query_one("#init-summary", Static).update(f"[red]✗ template fetch failed: {msg}[/red]")

    def _stage_local(self, ref: LocalTemplateRef) -> None:
        if self._gh_extract_dir and self._gh_extract_dir.exists():
            shutil.rmtree(self._gh_extract_dir, ignore_errors=True)
            self._gh_extract_dir = None
        files = enumerate_local_template_files(ref, scaffold_dir_relpaths=_SCAFFOLD_RELPATHS)
        self._injectables = files
        self._template_attribution = f"local: {ref.stem}"
        self._render_files_table()
        total_bytes = sum(f.size_bytes for f in files)
        self.query_one("#init-summary", Static).update(
            f"[green]✓[/green] {len(files)} files staged ({total_bytes / 1024:.1f} KB)"
        )
        self._refresh_apply_state()

    def _render_files_table(self) -> None:
        tbl = self.query_one("#init-files", DataTable)
        tbl.clear()
        for f in self._injectables:
            mark = "✓" if f.selected else " "
            size = f"{f.size_bytes} B" if f.size_bytes < 1024 else f"{f.size_bytes / 1024:.1f} KB"
            tbl.add_row(mark, str(f.dest_relpath), size, f.origin)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        idx = event.cursor_row
        if 0 <= idx < len(self._injectables):
            self._injectables[idx].selected = not self._injectables[idx].selected
            tbl = self.query_one("#init-files", DataTable)
            mark = "✓" if self._injectables[idx].selected else " "
            tbl.update_cell_at(Coordinate(idx, 0), mark)

    def _validate_name(self) -> tuple[bool, str]:
        name = self.query_one("#init-name", Input).value.strip()
        if not name:
            return False, "[dim]Enter a project name.[/dim]"
        if not _NAME_RE.match(name):
            return False, "[red]Name must match [A-Za-z0-9._-] and be 1–64 chars.[/red]"
        if name.upper() in _WIN_RESERVED:
            return False, f"[red]{name!r} is a Windows-reserved name.[/red]"
        parent = Path(self.query_one("#init-parent", Input).value).expanduser()
        if not parent.is_dir():
            return False, "[red]Parent dir does not exist.[/red]"
        target = parent / name
        if not _target_is_empty_or_only_mcp_json(target):
            return False, f"[red]{target} exists and is not empty.[/red]"
        return True, f"[green]✓[/green] Target: {target}"

    def _refresh_apply_state(self) -> None:
        ok, msg = self._validate_name()
        self.query_one("#init-name-status", Static).update(msg)
        has_files = bool(self._injectables)
        enabled = ok and has_files and not self._apply_in_progress
        self.query_one("#init-apply", Button).disabled = not enabled
        self.query_one("#init-edit-mcp", Button).disabled = not (ok and has_files)

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refresh_apply_state()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        bid = event.pressed.id or ""
        if bid == "init-source-local":
            self._populate_local()
        elif bid == "init-source-github":
            if self._gh_templates:
                self._on_gh_templates(self._gh_templates)
            else:
                self.query_one("#init-template-status", Static).update(
                    "[yellow]No GitHub template repos available — switch to local.[/yellow]"
                )

    def action_apply(self) -> None:
        ok, msg = self._validate_name()
        if not ok:
            self.query_one("#init-status", Static).update(msg)
            return
        if not self._injectables:
            self.query_one("#init-status", Static).update(
                "[red]No files staged — pick a template first.[/red]"
            )
            return
        self.query_one("#init-status", Static).update(
            "[yellow]Applying… (files → .gitignore → INIT_PROMPT → claude)[/yellow]"
        )
        self._apply_in_progress = True
        self._cancel_requested = False
        self._refresh_apply_state()
        self.run_worker(self._apply_worker, thread=True, exclusive=True)

    def _apply_worker(self) -> None:
        try:
            parent = Path(self.query_one("#init-parent", Input).value).expanduser()
            name = self.query_one("#init-name", Input).value.strip()
            target = parent / name

            report = apply_plan(target, self._injectables)

            added, tracked = ensure_mcp_gitignored(target)
            report.gitignore_added = added
            report.gitignore_already_tracked = tracked
            report.mcp_entries = count_project_mcp_entries(target)

            files_written = [str(inj.dest_relpath) for inj in self._injectables if inj.selected]
            agents_dir = target / ".claude" / "agents"
            skills_dir = target / ".claude" / "skills"
            cmds_dir = target / ".claude" / "commands"
            agents = sorted(p.stem for p in agents_dir.glob("*.md")) if agents_dir.is_dir() else []
            skills = sorted(p.stem for p in skills_dir.glob("*.md")) if skills_dir.is_dir() else []
            commands = sorted(p.stem for p in cmds_dir.glob("*.md")) if cmds_dir.is_dir() else []
            prompt = build_init_prompt(target, self._template_attribution, files_written, agents, skills, commands)
            write_init_prompt(target, prompt)

            if not shutil.which("claude"):
                report.claude_run = None
                self.app.call_from_thread(self._on_apply_done, report, None)
                return

            try:
                proc = spawn_claude(args=["-p", prompt], cwd=target)
            except FileNotFoundError:
                report.claude_run = ClaudeRunResult(returncode=127, stdout="", stderr="claude CLI not found in PATH")
                self.app.call_from_thread(self._on_apply_done, report, None)
                return

            self._claude_proc = proc
            out_lines: list[str] = []
            try:
                assert proc.stdout is not None
                for line in iter(proc.stdout.readline, ""):
                    s = line.rstrip()
                    if s:
                        out_lines.append(s)
                        self.app.call_from_thread(self._append_status_line, s)
                rc = proc.wait()
            finally:
                self._claude_proc = None
            err = proc.stderr.read() if proc.stderr else ""
            run = ClaudeRunResult(returncode=rc, stdout="\n".join(out_lines), stderr=err, cancelled=self._cancel_requested)
            self._cancel_requested = False
            report.claude_run = run
            self.app.call_from_thread(self._on_apply_done, report, None)
        except Exception as e:
            self.app.call_from_thread(self._on_apply_done, None, str(e))

    def _append_status_line(self, line: str) -> None:
        cur = str(self.query_one("#init-status", Static).render())
        lines = cur.splitlines()
        lines.append(line)
        if len(lines) > 20:
            lines = lines[-20:]
        self.query_one("#init-status", Static).update("\n".join(lines))

    def _on_apply_done(self, report: ApplyReport | None, error: str | None) -> None:
        self._apply_in_progress = False
        self._refresh_apply_state()
        if error or report is None:
            self.query_one("#init-status", Static).update(f"[red]✗ Apply failed: {error or 'unknown error'}[/red]")
            return
        msgs = [f"[green]✓[/green] Files written: {report.files_written} ({report.bytes_written / 1024:.1f} KB)"]
        if report.gitignore_added:
            msgs.append("[green]✓[/green] `.mcp.json` added to `.gitignore`")
        if report.gitignore_already_tracked:
            msgs.append("[yellow].mcp.json was already tracked by git in this repo — run `git rm --cached .mcp.json` to stop tracking it.[/yellow]")
        if report.mcp_entries:
            msgs.append(f"[green]✓[/green] Project MCP entries: {report.mcp_entries}")
        if report.claude_run is None:
            msgs.append("[yellow]claude CLI not installed — skipping architecture step. Install from Tools screen.[/yellow]")
        else:
            rc = report.claude_run.returncode
            if report.claude_run.cancelled:
                msgs.append("[yellow]cancelled[/yellow]")
            elif rc == 0:
                msgs.append("[green]✓ claude finished[/green]")
            else:
                msgs.append(f"[yellow]claude exited {rc} — review .claude/ manually[/yellow]")
        self.query_one("#init-status", Static).update("\n".join(msgs))

    def _open_browser(self) -> None:
        from cabal.views.folder_browser import FolderBrowserScreen
        raw = self.query_one("#init-parent", Input).value
        start = Path(raw).expanduser()
        if not start.is_dir():
            start = Path.cwd()

        def _cb(path: Path | None) -> None:
            if path is not None:
                self.query_one("#init-parent", Input).value = str(path)
                self._refresh_apply_state()

        self.app.push_screen(FolderBrowserScreen(start), _cb)

    def _open_project_mcp(self) -> None:
        ok, msg = self._validate_name()
        if not ok:
            self.query_one("#init-status", Static).update(msg)
            return
        parent = Path(self.query_one("#init-parent", Input).value).expanduser()
        name = self.query_one("#init-name", Input).value.strip()
        target = parent / name
        from cabal.views.project_mcp import ProjectMcpScreen

        def _on_mcp_change(count: int) -> None:
            self._mcp_entries_count = count
            self.query_one("#init-mcp-summary", Static).update(
                f"[dim]Project MCP entries staged: {count}[/dim]"
            )

        self.app.push_screen(ProjectMcpScreen(target_dir=target, on_change=_on_mcp_change))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "init-back":
            self.app.pop_screen()
        elif bid == "init-browse":
            self._open_browser()
        elif bid == "init-edit-mcp":
            self._open_project_mcp()
        elif bid == "init-apply":
            self.action_apply()
        elif bid == "init-cancel":
            if self._claude_proc and self._claude_proc.poll() is None:
                self._cancel_requested = True
                try:
                    self._claude_proc.terminate()
                except Exception:
                    pass
                self.query_one("#init-status", Static).update("[yellow]cancelled[/yellow]")
            else:
                self.app.pop_screen()

    def on_unmount(self) -> None:
        if self._gh_extract_dir and self._gh_extract_dir.exists():
            shutil.rmtree(self._gh_extract_dir, ignore_errors=True)
