# -*- coding: utf-8 -*-
"""SessionsScreen — browse, inspect, and delete Claude Code session transcripts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

from cabal.app_widgets import AppHeader
from cabal.models.session import AgentInvocation, Session, SessionSummary, SkillInvocation, ToolInvocation
from cabal.session_pricing import load_pricing
from cabal.session_reader import (
    compute_summary,
    delete_session,
    infer_session_tree,
    read_session,
    read_write_audit,
    scan_projects_dir,
)

_PROJECTS_DIR = Path.home() / ".claude" / "projects"
_AUDIT_PATH = Path.home() / ".claude" / "write_audit.jsonl"
_SORT_KEYS = ("date", "cost", "tokens")


def _build_tree_order(
    summaries: list[SessionSummary],
    lookup: dict[str, SessionSummary],
) -> list[tuple[SessionSummary, int]]:
    """Return (summary, depth) pairs: root sessions in sort order, each followed by children."""
    roots = [s for s in summaries if not s.parent_session_id]
    result: list[tuple[SessionSummary, int]] = []
    for root in roots:
        result.append((root, 0))
        _collect_children(root, lookup, result, 1)
    return result


def _collect_children(
    parent: SessionSummary,
    lookup: dict[str, SessionSummary],
    result: list[tuple[SessionSummary, int]],
    depth: int,
) -> None:
    for child_id in parent.child_session_ids:
        child = lookup.get(child_id)
        if child:
            result.append((child, depth))
            _collect_children(child, lookup, result, depth + 1)


class DeleteConfirmModal(ModalScreen[bool]):
    """Confirmation dialog before deleting a session."""

    DEFAULT_CSS = """
    DeleteConfirmModal > Vertical {
        width: 60;
        height: auto;
        padding: 2 4;
        background: $surface;
        border: round $error;
        margin: 4 auto;
    }
    DeleteConfirmModal Label { margin-bottom: 1; }
    DeleteConfirmModal Horizontal { height: auto; align: center middle; margin-top: 1; }
    DeleteConfirmModal Button { margin: 0 1; }
    """

    def __init__(self, session_id: str) -> None:
        super().__init__()
        self._session_id = session_id

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(
                f"[bold red]Delete session[/bold red]\n"
                f"[dim]{self._session_id}[/dim]\n\n"
                "This permanently removes the log file from disk.",
                markup=True,
            )
            with Horizontal():
                yield Button("Delete", id="confirm", variant="error")
                yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


class SessionsScreen(Screen):
    """Browse, inspect, and delete Claude Code session transcripts."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("d", "delete_selected", "Delete session"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "cycle_sort", "Sort"),
    ]

    DEFAULT_CSS = """
    SessionsScreen { layout: vertical; }
    #sessions-list { height: 14; border: round $primary; margin: 1 2 0 2; }
    #detail-area { height: 1fr; margin: 0 2 1 2; }
    #totals-bar {
        height: 2; margin: 0 2; padding: 0 1;
        background: $boost; border-bottom: solid $primary;
    }
    #empty-msg { content-align: center middle; height: 6; color: $text-muted; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 1; }
    .detail-table { height: 1fr; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._sessions: list[Session] = []
        self._summaries: list[SessionSummary] = []
        self._pricing = load_pricing()
        self._sort_idx = 0
        self._selected_summary: SessionSummary | None = None

    def compose(self) -> ComposeResult:
        yield AppHeader(show_clock=False)
        yield Static("", id="totals-bar")
        tbl = DataTable(id="sessions-list", cursor_type="row")
        tbl.add_columns("Title / Project", "Branch", "Date", "Cost USD", "Tools", "Errs", "Agents")
        yield tbl
        with TabbedContent(id="detail-area"):
            with TabPane("Overview", id="tab-overview"):
                yield VerticalScroll(Static("[dim]Select a session.[/dim]", id="overview-body"))
            with TabPane("Activity", id="tab-agents"):
                yield VerticalScroll(Static("[dim]Select a session.[/dim]", id="agents-body"))
            with TabPane("Raw Logs", id="tab-raw"):
                raw = DataTable(id="raw-table", cursor_type="row")
                raw.add_columns("Type", "Time", "Content")
                yield raw
            with TabPane("Triggers", id="tab-triggers"):
                trig = DataTable(id="triggers-table", cursor_type="row")
                trig.add_columns("Time", "Tool", "Path")
                yield trig
        yield Footer()

    def on_mount(self) -> None:
        self._load_sessions()

    def _load_sessions(self) -> None:
        self._sessions = scan_projects_dir(_PROJECTS_DIR)
        self._summaries = []
        for sess in self._sessions:
            entries = read_session(sess)
            self._summaries.append(compute_summary(sess, entries, self._pricing))
        infer_session_tree(self._summaries)
        self._sort_summaries()
        self._render_list()
        self._render_totals()

    def _sort_summaries(self) -> None:
        key = _SORT_KEYS[self._sort_idx % len(_SORT_KEYS)]
        if key == "date":
            self._summaries.sort(key=lambda s: s.start_time or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        elif key == "cost":
            self._summaries.sort(key=lambda s: s.estimated_cost_usd, reverse=True)
        elif key == "tokens":
            self._summaries.sort(key=lambda s: s.total_input_tokens + s.total_output_tokens, reverse=True)

    def _render_list(self) -> None:
        tbl = self.query_one("#sessions-list", DataTable)
        tbl.clear()
        if not self._summaries:
            return
        lookup = {s.session_id: s for s in self._summaries}
        ordered = _build_tree_order(self._summaries, lookup)
        for s, depth in ordered:
            date_str = s.start_time.strftime("%Y-%m-%d %H:%M") if s.start_time else "—"
            prefix = "  ↳ " * depth
            label = prefix + (s.title or s.project_path)
            tbl.add_row(
                label[:36],
                s.git_branch or "—",
                date_str,
                f"${s.estimated_cost_usd:.4f}",
                str(len(s.tool_calls)),
                str(s.tool_error_count) if s.tool_error_count else "—",
                str(s.agent_count),
                key=s.session_id,
            )

    def _render_totals(self) -> None:
        total_in = sum(s.total_input_tokens for s in self._summaries)
        total_out = sum(s.total_output_tokens for s in self._summaries)
        total_cost = sum(s.estimated_cost_usd for s in self._summaries)
        sort_key = _SORT_KEYS[self._sort_idx % len(_SORT_KEYS)]
        self.query_one("#totals-bar", Static).update(
            f"[bold]{len(self._summaries)}[/bold] sessions  ·  "
            f"[bold]{total_in:,}[/bold] in  ·  [bold]{total_out:,}[/bold] out  ·  "
            f"[bold]${total_cost:.2f}[/bold] total  ·  "
            f"[dim]sort: {sort_key}[/dim]  [dim](S to cycle, D to delete, R to refresh)[/dim]"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "sessions-list":
            return
        session_id = str(event.row_key.value) if event.row_key else None
        if not session_id:
            return
        summary = next((s for s in self._summaries if s.session_id == session_id), None)
        if not summary:
            return
        self._selected_summary = summary
        session = next((s for s in self._sessions if s.session_id == session_id), None)
        self._render_overview(summary)
        self._render_agents_tab(summary)
        if session:
            self._render_raw_tab(session)
            self._render_triggers_tab(summary)

    def _render_overview(self, s: SessionSummary) -> None:
        lines = []
        if s.title:
            lines.append(f"[bold]Title:[/bold]   {s.title}")
        lines += [
            f"[bold]Session:[/bold] {s.session_id}",
            f"[bold]Project:[/bold] {s.project_path}",
        ]
        if s.cwd:
            lines.append(f"[bold]Dir:[/bold]     {s.cwd}")
        if s.git_branch:
            lines.append(f"[bold]Branch:[/bold]  {s.git_branch}")
        if s.claude_version:
            lines.append(f"[bold]Version:[/bold] Claude Code {s.claude_version}")
        lines += [
            f"[bold]Date:[/bold]    {s.start_time.strftime('%Y-%m-%d %H:%M:%S UTC') if s.start_time else '—'}",
            f"[bold]Duration:[/bold] {s.duration_seconds:.0f}s",
            f"[bold]Messages:[/bold] {s.message_count}",
            "",
            "[bold]Activity summary:[/bold]",
            f"  Tool calls:    {len(s.tool_calls)}",
            f"  Files written: {s.files_written}",
            f"  Tool errors:   {s.tool_error_count}",
            f"  Agents:        {s.agent_count}",
            f"  Skills:        {len(s.skills)}",
            f"  Hook events:   {len(s.hook_events)}",
            "",
            "[bold]Token breakdown:[/bold]",
            f"  Input:       {s.total_input_tokens:,}",
            f"  Output:      {s.total_output_tokens:,}",
            f"  Cache read:  {s.total_cache_read_tokens:,}",
            f"  Cache write: {s.total_cache_write_tokens:,}",
            f"  [bold]Est. cost:   ${s.estimated_cost_usd:.6f}[/bold]",
            "",
            "[bold]Per-model breakdown:[/bold]",
        ]
        for model, usage in s.model_breakdown.items():
            lines.append(
                f"  [cyan]{model}[/cyan]"
                f"  {usage.input_tokens:,} in / {usage.output_tokens:,} out"
            )
        self.query_one("#overview-body", Static).update(Text.from_markup("\n".join(lines)))

    def _render_agents_tab(self, s: SessionSummary) -> None:
        from collections import Counter
        lines: list[str] = []

        # ── Skills ───────────────────────────────────────────────────────────
        lines.append(f"[bold]Skills invoked ({len(s.skills)}):[/bold]")
        if s.skills:
            for sk in s.skills:
                ts = sk.timestamp.strftime("%H:%M:%S") if sk.timestamp else "—"
                lines.append(f"  [{ts}] [magenta]/{sk.skill_name}[/magenta] {sk.args[:60]}")
        else:
            lines.append("  [dim]none detected[/dim]")

        # ── Agents ───────────────────────────────────────────────────────────
        lines.append("")
        lines.append(f"[bold]Agents dispatched ({s.agent_count}):[/bold]")
        if s.agents:
            for a in s.agents:
                ts = a.timestamp.strftime("%H:%M:%S") if a.timestamp else "—"
                model_tag = f"  [dim]{a.model}[/dim]" if a.model else ""
                lines.append(
                    f"  [{ts}] [cyan]{a.agent_type}[/cyan]{model_tag}"
                    f"  ← [yellow]{a.triggered_by}[/yellow]"
                )
                if a.description:
                    lines.append(f"    {a.description[:90]}")
        else:
            lines.append("  [dim]none detected[/dim]")

        # ── Tools ─────────────────────────────────────────────────────────────
        lines.append("")
        lines.append(f"[bold]Tool calls ({len(s.tool_calls)}):[/bold]")
        if s.tool_calls:
            counts: Counter[str] = Counter(t.tool_name for t in s.tool_calls)
            summary_parts = [f"[green]{name}[/green]×{n}" for name, n in counts.most_common()]
            lines.append("  " + "  ".join(summary_parts))
            lines.append("")
            for t in s.tool_calls[:200]:
                ts = t.timestamp.strftime("%H:%M:%S") if t.timestamp else "—"
                preview = t.input_preview[:70] if t.input_preview else ""
                lines.append(f"  [{ts}] [green]{t.tool_name}[/green]  {preview}")
        else:
            lines.append("  [dim]none detected[/dim]")

        # ── Hook Events ───────────────────────────────────────────────────────
        lines.append("")
        lines.append(f"[bold]Hook events ({len(s.hook_events)}):[/bold]")
        if s.hook_events:
            for h in s.hook_events:
                ts = h.timestamp.strftime("%H:%M:%S") if h.timestamp else "—"
                status = "[green]ok[/green]" if h.exit_code == 0 else f"[red]exit {h.exit_code}[/red]"
                lines.append(
                    f"  [{ts}] [magenta]{h.hook_event_type}[/magenta]:{h.hook_name}"
                    f"  {status}  ({h.duration_ms}ms)"
                )
        else:
            lines.append("  [dim]none[/dim]")

        # ── Subagent Sessions (inferred by time containment) ──────────────────
        if s.child_session_ids:
            lines.append("")
            lines.append(f"[bold]Subagent sessions — inferred ({len(s.child_session_ids)}):[/bold]")
            lookup = {c.session_id: c for c in self._summaries}
            for child_id in s.child_session_ids:
                child = lookup.get(child_id)
                if not child:
                    continue
                title = child.title or child.session_id[:12]
                dur = f"{child.duration_seconds:.0f}s"
                lines.append(
                    f"  [cyan]{title}[/cyan]"
                    f"  {dur}"
                    f"  {len(child.tool_calls)} tools"
                    f"  {child.agent_count} agents"
                    f"  {child.total_input_tokens:,} in / {child.total_output_tokens:,} out"
                    f"  [bold]${child.estimated_cost_usd:.4f}[/bold]"
                )
                for a in child.agents:
                    ts = a.timestamp.strftime("%H:%M:%S") if a.timestamp else "—"
                    model_tag = f"  [dim]{a.model}[/dim]" if a.model else ""
                    lines.append(
                        f"    [{ts}] [cyan]{a.agent_type}[/cyan]{model_tag}"
                        f"  {a.description[:70]}"
                    )

        self.query_one("#agents-body", Static).update(Text.from_markup("\n".join(lines)))

    def _render_raw_tab(self, session: Session) -> None:
        entries = read_session(session)
        tbl = self.query_one("#raw-table", DataTable)
        tbl.clear()
        for e in entries[:500]:
            ts = e.timestamp.strftime("%H:%M:%S") if e.timestamp else "—"
            content_preview = ""
            if isinstance(e.content, str):
                content_preview = e.content[:60].replace("\n", " ")
            elif e.tool_name:
                content_preview = f"[{e.tool_name}]"
            tbl.add_row(e.type, ts, content_preview)

    def _render_triggers_tab(self, summary: SessionSummary) -> None:
        since = summary.start_time
        events = read_write_audit(_AUDIT_PATH, since=since)
        end = summary.start_time
        if end and summary.duration_seconds:
            from datetime import timedelta
            end = end + timedelta(seconds=summary.duration_seconds + 60)
        filtered = [e for e in events if not end or e.timestamp <= end]
        tbl = self.query_one("#triggers-table", DataTable)
        tbl.clear()
        for e in filtered[:200]:
            tbl.add_row(e.timestamp.strftime("%H:%M:%S"), e.tool, e.path[-60:])

    def action_delete_selected(self) -> None:
        if not self._selected_summary:
            return
        summary = self._selected_summary

        def _on_confirmed(confirmed: bool | None) -> None:
            if not confirmed:
                return
            session = next((s for s in self._sessions if s.session_id == summary.session_id), None)
            if session:
                delete_session(session)
            self._selected_summary = None
            self._load_sessions()

        self.app.push_screen(DeleteConfirmModal(summary.session_id), _on_confirmed)

    def action_refresh(self) -> None:
        self._load_sessions()

    def action_cycle_sort(self) -> None:
        self._sort_idx += 1
        self._sort_summaries()
        self._render_list()
        self._render_totals()
