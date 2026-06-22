# -*- coding: utf-8 -*-
"""FileViewerModal — read-only modal that previews a file or a repo-vs-deployed diff.

Markdown renders via `MarkdownViewer`; everything else shows in a read-only,
syntax-highlighted `TextArea`. When a `compare_path` is supplied and its content
differs from the repo file, the modal opens on a coloured word-level diff and `d`
toggles between the diff and the full source. Used by the Global Claude Settings table.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, MarkdownViewer, Static, TextArea

from cabal.diff_text import render_word_diff

_LANG_BY_SUFFIX = {
    ".py": "python",
    ".json": "json",
    ".sh": "bash",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".css": "css",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".html": "html",
}
_MARKDOWN_SUFFIXES = (".md", ".markdown")
_MAX_BYTES = 400_000


class FileViewerModal(ModalScreen):
    """Centered modal previewing one file's content, or a deployed→repo diff."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("d", "toggle_diff", "Diff/Source"),
    ]

    CSS = """
    FileViewerModal { align: center middle; }
    FileViewerModal #fv-box {
        width: 90%;
        height: 90%;
        background: $surface;
        border: round $accent;
        padding: 1 2;
    }
    FileViewerModal #fv-title {
        text-style: bold;
        color: #5FAFFF;
        height: auto;
        margin: 0 0 1 0;
    }
    FileViewerModal #fv-content { height: 1fr; }
    FileViewerModal #fv-actions { height: auto; margin: 1 0 0 0; }
    FileViewerModal #fv-actions Button { margin: 0 1 0 0; }
    """

    def __init__(
        self,
        path: Path,
        title: str | None = None,
        *,
        compare_path: Path | None = None,
        new_text: str | None = None,
        diff_label: str = "deployed -> repo",
    ) -> None:
        super().__init__()
        self._path = path
        self._title = title or str(path)
        self._compare_path = compare_path
        self._new_text = new_text
        self._diff_label = diff_label
        self._diff_available = self._compute_diff_available()
        self._show_diff = self._diff_available

    def _compute_diff_available(self) -> bool:
        if self._compare_path is None or not self._compare_path.is_file():
            return False
        old = self._read_text(self._compare_path)[0]
        new = (
            self._new_text
            if self._new_text is not None
            else self._read_text(self._path)[0]
        )
        return old != new

    def compose(self) -> ComposeResult:
        with Vertical(id="fv-box"):
            yield Static("", id="fv-title")
            yield VerticalScroll(id="fv-content")
            with Horizontal(id="fv-actions"):
                if self._diff_available:
                    yield Button("Toggle diff (d)", id="fv-toggle", variant="default")
                yield Button("Close (Esc)", id="fv-close", variant="primary")

    async def on_mount(self) -> None:
        await self._populate_content()

    async def _populate_content(self) -> None:
        self.query_one("#fv-title", Static).update(self._title_text())
        box = self.query_one("#fv-content", VerticalScroll)
        await box.remove_children()
        if self._show_diff and self._diff_available:
            await box.mount(Static(self._diff_text(), id="fv-body"))
        else:
            await box.mount(self._build_content())

    def _title_text(self) -> str:
        if not self._diff_available:
            return f"📄 {self._title}"
        mode = f"diff: {self._diff_label}" if self._show_diff else "full source"
        return f"📄 {self._title}  [dim]·[/dim] [yellow]{mode}[/yellow]"

    def _build_content(self) -> Widget:
        text = (
            self._new_text
            if self._new_text is not None
            else self._read_text(self._path)[0]
        )
        err = self._read_text(self._path)[1] if self._new_text is None else None
        if err:
            return Static(f"[red]{err}[/red]", id="fv-body")
        if self._path.suffix.lower() in _MARKDOWN_SUFFIXES:
            return MarkdownViewer(text, show_table_of_contents=False, id="fv-body")
        lang = _LANG_BY_SUFFIX.get(self._path.suffix.lower())
        try:
            return TextArea.code_editor(
                text, language=lang, read_only=True, id="fv-body"
            )
        except Exception:
            # Requested grammar not bundled — fall back to plain read-only text.
            return TextArea.code_editor(text, read_only=True, id="fv-body")

    def _diff_text(self) -> Text:
        old = self._read_text(self._compare_path)[0]
        new = (
            self._new_text
            if self._new_text is not None
            else self._read_text(self._path)[0]
        )
        return render_word_diff(old, new)

    @staticmethod
    def _read_text(path: Path) -> tuple[str, str | None]:
        try:
            if not path.is_file():
                return "", f"Not a file: {path}"
            size = path.stat().st_size
            if size > _MAX_BYTES:
                return "", f"File too large to preview ({size:,} bytes): {path}"
            return path.read_text(encoding="utf-8", errors="replace"), None
        except OSError as e:
            return "", f"Could not read {path}: {e}"

    async def action_toggle_diff(self) -> None:
        if not self._diff_available:
            return
        self._show_diff = not self._show_diff
        await self._populate_content()

    def action_close(self) -> None:
        self.dismiss()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fv-close":
            event.stop()
            self.dismiss()
        elif event.button.id == "fv-toggle":
            event.stop()
            await self.action_toggle_diff()
