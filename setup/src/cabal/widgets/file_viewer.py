# -*- coding: utf-8 -*-
"""FileViewerModal — read-only modal that previews a file.

Markdown renders via `MarkdownViewer`; everything else shows in a read-only,
syntax-highlighted `TextArea`. Used by the Global Claude Settings table.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, MarkdownViewer, Static, TextArea

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
    """Centered modal previewing one file's content."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
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
    FileViewerModal #fv-close { margin: 1 0 0 0; }
    """

    def __init__(self, path: Path, title: str | None = None) -> None:
        super().__init__()
        self._path = path
        self._title = title or str(path)

    def compose(self) -> ComposeResult:
        with Vertical(id="fv-box"):
            yield Static(f"📄 {self._title}", id="fv-title")
            yield self._build_content()
            yield Button("Close (Esc)", id="fv-close", variant="primary")

    def _build_content(self) -> Widget:
        text, err = self._read()
        if err:
            return Static(f"[red]{err}[/red]", id="fv-content")
        if self._path.suffix.lower() in _MARKDOWN_SUFFIXES:
            return MarkdownViewer(text, show_table_of_contents=False, id="fv-content")
        lang = _LANG_BY_SUFFIX.get(self._path.suffix.lower())
        try:
            return TextArea.code_editor(
                text, language=lang, read_only=True, id="fv-content"
            )
        except Exception:
            # Requested grammar not bundled — fall back to plain read-only text.
            return TextArea.code_editor(text, read_only=True, id="fv-content")

    def _read(self) -> tuple[str, str | None]:
        try:
            if not self._path.is_file():
                return "", f"Not a file: {self._path}"
            size = self._path.stat().st_size
            if size > _MAX_BYTES:
                return "", f"File too large to preview ({size:,} bytes): {self._path}"
            return self._path.read_text(encoding="utf-8", errors="replace"), None
        except OSError as e:
            return "", f"Could not read {self._path}: {e}"

    def action_close(self) -> None:
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fv-close":
            event.stop()
            self.dismiss()
