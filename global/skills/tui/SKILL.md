---
name: tui
description: Textual TUI lessons learned from building the cabal wizard. Use PROACTIVELY when building or modifying any Textual (or other Python terminal UI) app — "build a TUI", "terminal app", "add a screen", new widgets, keybindings, clipboard handling, or subprocess-spawning views. Covers the Ctrl+C-is-copy-everywhere rule, OS clipboard integration, base-class shadow traps, Pilot smoke tests, and child-process lifecycle. Pairs with @python-architect for app structure and @python-tester for the test suite.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# /tui — Textual terminal-UI conventions

Hard-won rules from the cabal TUI in prompt-lib. Every one of these caused a real bug; none of them are theoretical.

## Rule 1 — Ctrl+C is copy. Everywhere. Always.

The user must be able to press Ctrl+C on ANY view to copy selected text, and it must never terminate or interrupt the app. This has two independent halves — implementing only one still loses the app or the copy. (Enforced in prompt-lib by `.githooks/pre-commit`'s ctrl+c guard — any `"ctrl+c"` string in cabal source outside `app.py` blocks the commit; bypass a legitimate line with `# noqa: ctrl-c-binding`. Runtime guards live in `tests/integration/test_ctrl_c_copy_guard.py`.)

**Key level** — never bind `ctrl+c` to quit/exit. Textual ≥ 8 routes it to native copy; binding it to quit kills the app on every copy attempt. Quit is `ctrl+q` (shown in footer) plus `q`:

```python
BINDINGS = [
    Binding("ctrl+q", "quit", "Quit", show=True),
    Binding("q", "quit", "Quit", show=False),
    Binding("ctrl+c,ctrl+shift+c", "copy", "Copy", show=False),
    Binding("ctrl+v,ctrl+shift+v", "paste", "Paste", show=False),
    Binding("ctrl+shift+a", "select_all", "Select all", show=False),
]
```

**OS level** — the real killer. On Windows, Ctrl+C pressed while a worker subprocess (winget / git / npm) shares the console sends `CTRL_C_EVENT` to the whole process group and takes the parent down even though Textual never saw the key. Ignore SIGINT at entry:

```python
def _suppress_sigint() -> None:
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except (ValueError, OSError):
        pass  # not the main thread, or no SIGINT on this platform

def main() -> None:
    _suppress_sigint()
    MyApp().run()
```

**App-level copy/paste actions** delegate to the focused widget first, then the screen, so the same keys work in inputs, text areas, and plain selectable views:

```python
async def action_copy(self) -> None:
    focused = self.focused
    if focused is not None and await self.run_action("copy", focused):
        return
    if await self.run_action("screen.copy_text"):
        return
    raise SkipAction()
```

## Rule 2 — Ctrl+V must read the OS clipboard

Textual's `Input.action_paste` reads only the app-internal buffer — external copies are invisible without an override. Override `App.clipboard` and mirror copies both ways, trimming the padding Textual's cell-based selection adds:

```python
@property
def clipboard(self) -> str:
    return read_clipboard() or self._clipboard  # OS first, internal fallback

def copy_to_clipboard(self, text: str) -> None:
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    super().copy_to_clipboard(text)
    write_clipboard(text)
```

Reference implementation: `setup/src/cabal/app.py` + `setup/src/cabal/clipboard.py` in prompt-lib.

## Rule 3 — Don't shadow Textual base-class internals

Single-underscore helpers named `_render*`, `_compose*`, `_on_*`, `_watch_*`, `_action_*`, `_arrange_*`, or `_get_*_lines` on a Widget/Screen subclass silently override framework methods and crash at layout time with misleading `Visual.to_strips` tracebacks — never at import time. Name helpers by role (`_build_status_text`, `_collect_rows`), never by framework verb. The documented user override is `render(self)`, no underscore. (Enforced in prompt-lib by `.githooks/pre-commit`; bypass a legitimate override with `# noqa: textual-shadow`.)

## Rule 4 — Smoke-test through the render pipeline

Every custom widget gets one mount-and-render test via `App.run_test()` / `Pilot` with at least one `await pilot.pause()`. Tests that call helper methods directly bypass layout and miss shadow bugs entirely. Assert on what the user sees (rendered text, tooltips, footer bindings), not on internal state.

## Rule 5 — Never orphan a child process

Every subprocess the app spawns must be terminated and its log handles closed on app exit — including quit-while-running. Track children centrally (a supervisor/registry, not per-view ad hoc `Popen`), and shut them down in the app's exit path. On Windows, spawn long-running children with `CREATE_NEW_PROCESS_GROUP` so console signals don't couple parent and child fates.

## Rule 6 — Screens stay thin

`compose()` + event handlers in the view; worker bodies (`_fetch_*`, `_apply_*`) in a sibling `<feature>_worker.py`; `subprocess`/git/HTTP in `<feature>_service.py`. Business logic never lives in a Screen. LoC budgets and split patterns: `~/.claude/rules/python.md`.

## Binding conventions

- `ctrl+q` quit (footer-visible), `q` quit, `escape` back/dismiss
- Arrow keys move focus where it doesn't conflict with widget-internal navigation
- Every screen's footer shows its real bindings — no hidden keys the user must guess
