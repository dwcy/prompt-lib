---
description: Python file conventions — loaded automatically when editing .py files. Numeric LoC budgets + 5 concern-separation triggers.
paths:
  - "**/*.py"
---

## File intent

Add a one-line module docstring at the top of every new file naming its single responsibility. Update it when the file's purpose changes.

## Numeric LoC budgets

| File kind | Soft cap | Hard cap |
|---|---:|---:|
| Python library module | 200 | 400 |
| Python view / Textual screen | 250 | 400 |
| Python script (`__main__.py`, `cli/*.py`) | 150 | 250 |
| Test module | 300 | 500 |

- **Soft cap** = stop and ask "does this file own one responsibility?" before adding more.
- **Hard cap** = split, OR write a justification comment at line 1: `# > 400 LoC justified: <one-line structural reason>`.
- "Needed", "complex", "for now" do NOT count as substantive reasons. The verifier audits this.

## The 5 concern-separation triggers

See `_size-discipline.md` for the canonical list. Two or more firing → split before writing.

Quick reminder applied to Python:

1. > 3 unrelated public symbols in one file.
2. Imports span > 5 logical domains (UI + `subprocess` + `pathlib` + `json` + `requests` + `sqlalchemy` is six).
3. > 15 methods on one class.
4. File approaches soft cap AND mixes UI (Textual / Tkinter / Streamlit) with side-effecting I/O (`subprocess`, network, `Path.write_text`).
5. Any method does > 2 context switches (parse → shell out → render).

## Split patterns

- **Service module** — extract `subprocess` / `git` / HTTP / DB calls into `<feature>_service.py`. The view imports `apply_plan(...)`, never `subprocess.run(...)`.
- **View + worker** — `cabal/views/<screen>.py` owns `compose()` + event handlers. Long worker bodies (`_fetch_*`, `_apply_*`) move into a sibling module the view imports.
- **Model + repository** — dataclass / Pydantic model in `models/<entity>.py`; persistence in `repositories/<entity>_repo.py`.
- **Builder + emitter** — large prompt / config / SQL string construction goes into `<feature>_builder.py`. The consumer just calls `build_X(...)`.
- **Facade re-exports** — when an old monolithic module had widely-used names, keep a thin facade that re-exports from the new modules. Example: `setup/src/cabal/wizard.py` is a 196-LoC facade after the 005 refactor.

## Legitimate bundling — when NOT to split

Inline justifications that pass the verifier:

- **Spec-required co-location** — e.g. `setup/src/cabal/app.py` holds the inline `CSS` blob per spec FR-5. Justified at line 1.
- **Single tightly-cohesive class** — a `Repository` with 12 method overloads for the same entity is fine; 12 method overloads PLUS an unrelated `EventBus` is not.
- **Generated files** — parser tables, lockfile snapshots, vendored helpers. Mark with a header comment.

## Hard rules to enforce

- Business logic never lives in routers, endpoints, or Textual screens.
- Settings always come from environment variables via `pydantic-settings` — no hardcoded config.
- All I/O in an async project must be async — flag blocking calls.
- Never `import *`.
- Use `pathlib.Path` not `os.path`.
- `from __future__ import annotations` at the top of every module.

## Textual widgets

When subclassing `textual.widget.Widget`, `textual.screen.Screen`, or any Textual base:

- **Do not name helpers with single-underscore framework verbs.** Reserved prefixes: `_render`, `_render_*`, `_compose`, `_compose_*`, `_on_*`, `_watch_*`, `_action_*`, `_get_*_lines`, `_arrange_*`. Python's single underscore is convention-only, so an override compiles silently and crashes at layout time with confusing `Visual.to_strips` / `_render_content` tracebacks — not at import time.
- **Documented user override is `render(self)` (no underscore).** Anything starting with `_` on a Textual base class is framework territory.
- **Name helpers by role, not by verb.** `_build_status_text`, `_format_body`, `_collect_rows` — these can never collide. `_render`, `_compose`, `_update` — these can.
- **Every custom widget needs one mount-and-render smoke test** using `App.run_test()` / `Pilot` with at least one `pilot.pause()`. Tests that call helper methods directly bypass the render pipeline and miss shadow bugs entirely.
- **Enforced by `.githooks/pre-commit`** in this repo: any staged `.py` file that subclasses a `textual.*` import is checked, and method names colliding with the resolved base class block the commit. Bypass a single legitimate override with `# noqa: textual-shadow` on the `def` line.

## Imports order

```python
# 1. stdlib
import json
import subprocess
from pathlib import Path

# 2. third-party
from textual.app import App
from rich.text import Text

# 3. first-party
from cabal._paths import GLOBAL_DIR
from cabal.claude_cli import _run_claude_cli
```

## Async patterns

- `async def` end-to-end if the surrounding stack is async — no `time.sleep`, no blocking `requests`.
- Every `await` has explicit error handling: `try/except`, `asyncio.gather(return_exceptions=True)`, or a typed result.
- Never silently swallow exceptions. Log or re-raise with context.

## Constants

- No magic strings or numbers inline — define at module top or in a `constants.py`.
- `Literal[...]` over free-form strings where the set of values is known.

## DRY and YAGNI

- Extract shared logic the second time you see it duplicated, not speculatively.
- Remove unused variables, imports, and dead code immediately — do not comment out.
- No TODO comments left in committed code — either do it now or open a task.
