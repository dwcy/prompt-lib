# Phase 0 — Research & Design Decisions

**Feature**: 005-cabal-tools-polish — Refactor `cabal/wizard.py` into Maintainable Modules
**Date**: 2026-05-28

This document captures the structural decisions taken before code moves. Each entry follows the spec-kit Decision / Rationale / Alternatives format.

## R1 — Why a flat-then-nested package layout instead of fully flat or fully nested?

**Decision**: Two folders only — `installers/` and `views/` (plus a small `widgets/`). Everything else lives directly under `cabal/`.

**Rationale**:
- The 24 installers and 17 screens are the only two clusters where the count is large enough to justify a subfolder. Forcing every concern into a folder (`cabal/banner/banner.py`) would multiply directories without improving navigation.
- Folders also act as a discovery signal: a maintainer looking for "where do screens live" expects a `views/` directory.

**Alternatives considered**:
- *Fully flat (`cabal/install_node.py`, `cabal/screen_home.py`)* — rejected. 40+ files in one directory makes IDE file-trees noisy.
- *Fully nested (one folder per concern)* — rejected. Too much boilerplate (`cabal/banner/__init__.py`) for a single-class module.

## R2 — Where does the CSS blob in `CabalApp.CSS` go?

**Decision**: Stays inline in `cabal/app.py` for now. No extraction.

**Rationale**:
- Moving it to `cabal/_data/app.tcss` requires a `pyproject.toml` change (data-file include rule) and an `importlib.resources` read at startup. Both are out-of-scope cost for v1.
- A sibling `cabal/app_css.py` that just defines `APP_CSS = """..."""` and re-imports it adds no actual benefit — it's still one big string, just in a different file.
- The blob (~145 lines) is tightly coupled to the screens it styles; co-locating it with `CabalApp` is fine.

**Alternatives considered**:
- *Move to `app_css.py` sibling* — rejected per above. No win.
- *Move to `_data/app.tcss` + `importlib.resources.read_text`* — rejected: requires `pyproject.toml` data-file include, PyInstaller spec data-file entry, and a startup read. Save for a future polish round.

## R3 — Should the installer registry use a decorator (`@register("node")`) or an explicit table?

**Decision**: Keep the existing explicit pattern. `_installer_for(key)` continues to be a `match`-style function that the refactor migrates to `cabal/tools.py`. No decorator framework.

**Rationale**:
- The current code is explicit and grep-able. A registry decorator hides the mapping behind module-import side effects.
- A decorator forces every installer module to be imported before `_installer_for` can resolve any key, which negates the "lazy import" benefit of having modules in the first place.

**Alternatives considered**:
- *`@register` decorator pattern* — rejected. Hides the wiring; tooling can't easily list installers without executing them.
- *Per-installer class with `key` attr* — rejected. Adds 24 classes for no behavior change.

## R4 — Order of extraction (which module first)?

**Decision**: Extract leaf-most modules first, work upward.

**Order**:
1. `_paths.py` (zero deps inside cabal — uses only stdlib + sys)
2. `os_filters.py` (zero internal deps)
3. `banner.py` (zero internal deps)
4. `env_summary.py` (zero internal deps; pure formatters)
5. `settings_helpers.py` (zero internal deps)
6. `components.py` (depends on `_paths.py` for `GLOBAL_DIR`, `TARGET`; on `os_filters.py`)
7. `env_detect.py` (uses `subprocess`, no internal deps beyond `_paths.py` for `_dotnet_sdks` env)
8. `diff_apply.py` (depends on `components.py`, `_paths.py`, `os_filters.py`, `settings_helpers.py`)
9. `gh_release.py` (depends on nothing internal)
10. `git_config.py` (depends on nothing internal beyond `_paths.py`)
11. `updates.py` (depends on `_paths.py`)
12. `mcp_ops.py` (depends on `_paths.py`)
13. `installers/_common.py` → individual installer files (each depends on `gh_release.py` and/or `_common.py`)
14. `tools.py` (depends on every `installers/*`)
15. `widgets/update_panel.py`, `widgets/env_panel.py` (depend on `updates.py`, `env_detect.py`, `tools.py`)
16. `screens/*` (depend on widgets, ops, mcp, etc.)
17. `app.py` (depends on screens)
18. `wizard.py` → facade (depends on everything; re-exports the public API)

**Rationale**: This order minimizes import cycles. Every extraction has its prerequisites already in place. A failed import surfaces immediately at the next smoketest run after the move.

**Alternatives considered**:
- *Top-down (extract `CabalApp` first)* — rejected. Would force every dependency to be in place before the first commit can compile, defeating the "one extraction per commit" rule.
- *Random / by-line-count* — rejected. Higher chance of mid-refactor circular imports.

## R5 — Should every screen import its sibling screens at module top, or lazily inside `action_*` methods?

**Decision**: Hybrid. Each screen module imports only the screens it directly pushes from `action_*` handlers — lazily, *inside the handler body*. This keeps module-top imports limited to widgets, helpers, and Textual.

**Rationale**:
- Module-top cross-screen imports create cycles fast (Home pushes Operations; Operations pushes Tools; Tools' "back" might push Home).
- Lazy imports inside method bodies are a recognized Textual pattern for the same reason.
- PyInstaller's static analyzer follows `cabal/app.py`'s top-level screen imports (R6) so lazy method-body imports don't break the bundled exe.

**Alternatives considered**:
- *All top-level imports everywhere* — rejected. Will trip cycles.
- *Single `cabal/views/__init__.py` that imports them all, then every screen imports from `cabal.views`* — rejected. Adds an extra hop and still risks cycles.

## R6 — How does PyInstaller find every screen if some are only referenced via lazy imports?

**Decision**: `cabal/app.py` imports every screen at module top, even ones it doesn't directly push. The reference is `_ = [HomeScreen, ReadmeScreen, EnvScreen, ...]` or equivalent — it exists so the static analyzer follows the import edge.

**Rationale**:
- PyInstaller traces module imports; it can't see strings or runtime `push_screen()` calls.
- A single anchor file (`app.py`) that names every screen guarantees the analyzer pulls them.
- Cheaper than maintaining a `hiddenimports = [...]` list in the spec.

**Alternatives considered**:
- *Extend `hiddenimports` in `cabal.spec`* — acceptable as a belt-and-suspenders second layer. Plan keeps both.
- *PyInstaller hook* (`hook-cabal.py`) — overkill for v1.

## R7 — Does the facade `wizard.py` use `from X import *` or explicit re-exports?

**Decision**: Explicit re-exports with a `__all__` list. No `import *`.

**Rationale**:
- `import *` re-exports whatever a submodule exposes — including stdlib names accidentally pulled in via `from pathlib import Path`. Explicit is grep-able and PyInstaller-friendly.
- The facade serves as the single canonical list of "what callers can rely on" — `contracts/public-api.contract.md` IS the `__all__`.

**Alternatives considered**:
- *Submodules + no facade (callers update to `from cabal.env_detect import detect_env`)* — rejected. Breaks the existing smoketest and PyInstaller spec; we explicitly require backward compatibility per FR-1.

## R8 — Where does the contract test live, and what does it assert?

**Decision**: `tests/contract/test_wizard_public_api.py`. Asserts, for every name listed in `contracts/public-api.contract.md`:

1. `getattr(cabal.wizard, name)` returns a non-None object.
2. `inspect.getmodule(getattr(cabal.wizard, name)).__name__` starts with `cabal.` (i.e. the symbol still belongs to this package, not an accidental re-export of a stdlib name).
3. For callables, calling `inspect.signature(...)` succeeds (cheap proof the object is real, not a typo'd attribute).

**Rationale**:
- Constitution Gate 3 requires contract tests for protocol surfaces. The wizard's public API isn't a wire protocol, but the same principle applies: the test exercises the surface other code talks to, not the in-process implementation.
- The contract test runs in CI (or by hand) before any extraction commit lands.

**Alternatives considered**:
- *No contract test, rely on the smoketest* — rejected. The smoketest only touches 4 of the ~25 grandfathered symbols. Easy to silently break the others.

## Open questions resolved during research

- **Q**: Does `pyproject.toml` need an update for the new submodules to ship in the wheel? **A**: No. `packages = ["setup/src/cabal"]` recurses; Hatchling picks up every `*.py` under that root.
- **Q**: Does the dev shim `setup/settings-configurator-ui.py` need a change? **A**: No. It imports `cabal.__main__:main`, which still calls `cabal.wizard.run`, which the facade re-exports.
- **Q**: Should `IS_FROZEN` move with `_resource_root` to `_paths.py`? **A**: Yes. It's a paths-layer concern. The facade re-exports it for any caller that read it before.

---

# Part B — Init Project, Project MCP, Claude Stats Panel

Added 2026-05-28 (spec extension). Decision/Rationale/Alternatives format follows.

## R9 — GitHub template fetch strategy

**Decision**: Use the user's already-authenticated `gh` CLI for both listing and downloading.

- **List**: `gh repo list --json isTemplate,name,owner,description,defaultBranchRef,url --limit 200` → filter `isTemplate == true`.
- **Fetch**: `gh api repos/<owner>/<repo>/tarball/<defaultBranch>` → stream into `tempfile.NamedTemporaryFile(suffix=".tar.gz")`, extract via `tarfile` into `tempfile.mkdtemp()`.

**Rationale**:

- `gh` is already a tool the user has (it's in `cabal/installers/gh.py`); no new pip dep (NFR-4).
- `gh api` handles auth (works for the user's own private template repos) — no plumbing of PATs through cabal.
- A tarball is one round-trip; local extract lets the preview table show the full tree without re-fetching per file.

**Alternatives considered**:

- *`gh repo clone`* — pulls full git history (megabytes), needs `.git` cleanup. Tarball is leaner.
- *Direct `https://api.github.com/repos/.../zipball/main` via `urllib`* — re-implements auth from `~/.config/gh/hosts.yml`. Rejected.
- *`gh api repos/.../contents/<path>` recursive* — one HTTP per file. Slow.

## R10 — `claude` CLI non-interactive invocation

**Decision**: Use `claude -p "<prompt>"` (the `--print` / `-p` flag). Run on a worker thread, capture stdout, expose Cancel via `Popen.terminate()`.

- **Argv**: `["claude", "-p", PROMPT]`
- **Subprocess**: `cwd=<new project>`, `stdin=DEVNULL`, `text=True`, `env={**os.environ, "MSYS_NO_PATHCONV": "1"}` (same shim as `mcp_ops._run_claude_cli`).
- **Dispatch**: `run_worker(self._invoke_claude, thread=True, exclusive=True)`.
- **Cancel**: `Popen(...)` not `run(...)` so we can `.terminate()` then `.kill()` after a 3 s grace.

**Rationale**:

- `-p` is the documented non-interactive entry. Stdin (`--prompt-stdin`) is also valid but adds plumbing — argv is enough (well under any OS argv limit).
- Re-uses the proven MSYS shim from `cabal/mcp_ops.py`.

**Alternatives considered**:

- *`claude --print --prompt-stdin`* — slightly more robust for huge prompts; not needed for v1.
- *Spawn `claude` inside `with self.app.suspend():`* like `LocalScreen` does for `specify init` — would block the wizard's other panels. Rejected — Apply should not take over the screen.

## R11 — Project-scope MCP store format

**Decision**: `<project>/.mcp.json` with shape `{"mcpServers": {<name>: <template-shape>}}`, matching the shape `cabal/mcp_ops.py:109-119` already reads for the `project` scope.

**Rationale**:

- We are writing in the same shape we already read — round-trip safe.
- The `template` dict consumed by `claude_mcp_add_from_template` can be serialised straight into this file (drop `transport`, `env_required`; keep `command`, `args`, `env`).

**Alternatives considered**:

- *Per-project `.claude.json`* — would shadow `~/.claude.json` and confuse Claude Code. Rejected.
- *Embed into `.claude/settings.local.json`* — that file is for permissions/hooks. Mixing scopes is a footgun. Rejected.

## R12 — Project name validation

**Decision**: Regex `^[A-Za-z0-9._-]{1,64}$` AND case-insensitive denylist of Windows-reserved names (`CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9`).

**Rationale**:

- POSIX-safe, GitHub-safe, easy to validate before Apply.
- Surfacing the Windows-reserved case is friendlier than letting `mkdir` raise `OSError` (R-8).

**Alternatives considered**:

- *Allow unicode* — Textual supports it, but downstream tooling (Git, gh) struggles. Rejected.

## R13 — Fallback when no GH templates / no `gh` / offline

**Decision**: Always offer the local `global/project-templates/*.md` set. On screen mount, dispatch a worker that runs `gh repo list --json isTemplate ...`. If it returns empty OR raises, pre-select `local` with a yellow status hint. Else pre-select `github`.

**Rationale**: Same template library `LocalScreen` already exposes — consistency. "Apply everything" default in the local case = CLAUDE.md from template + `.claude/` scaffold + matching `.gitignore` preset + `git_config` files.

**Alternatives considered**:

- *Hard fail when `gh` missing* — punishes offline scaffolding. Rejected.
- *Bundle a hardcoded fallback starter* — extra maintenance for marginal value. Rejected.

## R14 — Tar-slip / zip-slip protection

**Decision**: Before `tarfile.extractall()`, iterate `tar.getmembers()` and reject the whole archive if any member:

- has an absolute `name` (starts with `/`, `\`, or matches `^[A-Za-z]:`),
- contains `..` as a path segment,
- is a symlink or hardlink (`member.issym() or member.islnk()`).

On rejection, show `[red]Template archive rejected — unsafe paths.[/red]` and stay on screen.

**Rationale**: Python 3.12+ has `tarfile.data_filter`; we target 3.11+, so we do the check manually. We can opportunistically pass `filter="data"` too when `sys.version_info >= (3, 12)`.

**Alternatives considered**: *Trust `gh`-sourced tarballs* — `gh` is a transport, not a sanitizer. Rejected.

## R15 — Test strategy for Textual screens

**Decision**: Use `App.run_test()` (Textual's headless driver) for integration tests; mock `subprocess.run` / `subprocess.Popen` for `gh` and `claude`; use real `tempfile.mkdtemp()` and a small fixture tarball under `tests/fixtures/`.

**Rationale**: Official Textual test idiom; deterministic and offline; exercises the real tar-extract path.

**Alternatives considered**: *E2E against real GitHub + real `claude`* — flaky, slow, requires every contributor to have `gh` authed. Rejected for the default suite; can be `pytest -m e2e` later.

## R16 — Where the shared `_run_claude_cli` helper lives

**Decision**: Extract `_run_claude_cli` from `cabal/mcp_ops.py:40-52` into `cabal/claude_cli.py`; `mcp_ops.py` re-imports it. The new `claude_print()` for InitProject lives in the same module.

**Rationale**: DRY — one home for MSYS shim, exit-127 convention, timeout handling. `mcp_ops.py` keeps a narrow purpose.

## R17 — How the wizard hands off to Claude

**Decision**: Wizard writes a single prompt file at `<new project>/.claude/INIT_PROMPT.md` describing:

- Template used (GitHub repo URL OR local `global/project-templates/<stem>.md`).
- Files written.
- Agents/skills now in `<new project>/.claude/` (discovered by globbing `agents/*.md` and `skills/*.md`).
- Instruction: *"You are in a freshly initialised project. Follow the architecture template above and finish setting up `<project>` against the files in `.claude/`. Start by acknowledging the template and outlining what you'll do."*

Wizard then invokes `claude -p "$(read .claude/INIT_PROMPT.md)"`.

**Rationale**: File survives wizard exit so the user can re-run `claude -p < .claude/INIT_PROMPT.md`. Static prompt is auditable.

**Alternatives considered**: *Pass via `Popen.stdin`* — loses persistent record. Rejected.

## R18 — Claude stats panel (added 2026-05-28)

**Decision**: Add a nested panel to `HomeScreen`'s main area (right next to `EnvPanel`) — render in a new widget `cabal/widgets/claude_stats_panel.py`. Display:

- **Account type**: `Pro` / `Max 5x` / `Max 20x` / `Team` / `Enterprise` / `API` / `unknown` — read from `claude --print "/status"` output OR from `~/.claude.json["oauthAccount"]["organizationRole"]` / similar field if available; otherwise from `claude /login --print-account` if that subcommand exists.
- **Plan limits / usage**: 5-hour message count, weekly cap percentage, model fallback notes — parsed from `claude /status` non-interactively. If parsing fails, render `"stats unavailable — open `claude /status` directly"`.
- **Active model**: detected from `~/.claude.json["activeModel"]` (or equivalent — confirm at impl time).
- **Auth state**: `signed in as <email>` / `not signed in — run claude /login` — from `~/.claude.json["oauthAccount"]["emailAddress"]` if present.

**Refresh**: on `on_mount` and on a manual refresh button (`Ctrl+S`); never polled. The shell-out runs on a worker thread.

**Rationale**:

- `claude /status` is the documented non-interactive way to print account state; running it under `claude -p "/status"` keeps the same subprocess shape as the rest of the wizard.
- Reading `~/.claude.json` is a cheap fallback when the CLI isn't installed (NFR-6: never block the event loop, even by a missing binary).
- A nested panel in `HomeScreen` puts the info where the user already looks; no extra navigation.

**Fields not displayed**:

- API key value, OAuth token, refresh token — these are private. Show `present / not present`, never the value (Constitution IV adjacent — reversible config doesn't mean visible secrets).
- Per-message dollar cost — Claude's CLI doesn't surface that reliably; don't fake it.

**Alternatives considered**:

- *Separate `ClaudeStatsScreen` reached from a home button* — adds friction for info the user wants at a glance. Rejected.
- *Poll every N seconds* — pointless for slow-changing info (account type doesn't shift between TUI refreshes). Rejected.
- *Bundle stats into the existing `EnvPanel`* — `EnvPanel` is about installed tools; mixing in account/subscription info dilutes its purpose. Rejected — separate sibling panel.

**Risk added**:

- **R-9** — `claude /status` output format may change between Claude Code versions. Mitigation: parse defensively (regex pattern for `Account type: <X>`, `5-hour limit: <N>%`, etc.); on any parse failure, render the raw output verbatim inside the panel rather than a confident-but-wrong table. Note the supported `claude` minimum version in the panel footer.

---

**No NEEDS CLARIFICATION items remain for Part B.** Proceed to Phase 1.
