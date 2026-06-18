# Implementation Plan: Cabal Tools Polish — Refactor + Init Project Wizard

**Branch**: `005-cabal-tools-polish` | **Date**: 2026-05-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/005-cabal-tools-polish/spec.md`

## Summary

Two related deliverables on the same branch:

- **Part A — Refactor** `setup/src/cabal/wizard.py` from a single 4502-line file into a package of cohesive modules (`cabal.views.*`, `cabal.widgets.*`, `cabal.installers.*`, plus helper modules `cabal._paths`, `cabal.app`, `cabal.banner`, `cabal.components`, `cabal.diff_apply`, `cabal.env_detect`, `cabal.env_summary`, `cabal.git_config`, `cabal.mcp_ops`, `cabal.tools`, `cabal.updates`). The facade `cabal.wizard` re-exports every symbol the smoketest, PyInstaller spec, and external callers depend on. **Already largely landed** on this branch (`wizard.py` is now 196 lines).
- **Part B — Init Project wizard view + Claude Stats panel** adds (a) a home-screen entry point that scaffolds a brand-new project folder, applies a chosen template (a GitHub template repo or one of the local `global/project-templates/*.md`), edits per-project MCP, previews every file to be written, and invokes the `claude` CLI to apply the architecture template against the freshly created `.claude/`; and (b) a nested `ClaudeStatsPanel` on the home screen sibling to `EnvPanel` that shows account type, signed-in email, plan usage, and active model — parsed from `claude -p "/status"` with a `~/.claude.json` fallback.

Technical approach (Part B): one new screen (`cabal/views/init_project.py`), one mirror MCP screen (`cabal/views/project_mcp.py`), one new home-screen widget (`cabal/widgets/claude_stats_panel.py`), one helper module for GitHub template fetching (`cabal/gh_templates.py`), one helper for `claude -p` invocation (extracted from `cabal/mcp_ops.py` so all callers reuse the same `MSYS_NO_PATHCONV=1` wrapper), and one prompt-template module (`cabal/views/init_project_prompt.py`). Updates to `cabal/views/home.py` to add the two new "Project" entries and to mount the `ClaudeStatsPanel`. Hooks to `cabal/app.py` so PyInstaller's static analyzer discovers the new screens.

## Technical Context

**Language/Version**: Python 3.11+ (`pyproject.toml` declares `requires-python = ">=3.11"`).
**Primary Dependencies**: Textual ≥ 0.80 (TUI framework), Rich ≥ 13 (text rendering — Textual transitive), stdlib only beyond that (`subprocess`, `tarfile`, `tempfile`, `shutil`, `json`, `pathlib`, `os`, `re`, `platform`). No new pip dependency introduced.
**External tools (PATH only — not pip deps)**: `gh` ≥ 2.20 (for `--json isTemplate`), `claude` (the Claude Code CLI; optional — graceful fallback per FR-15), `git` (only for `git init` already used in `LocalScreen`).
**Storage**: Filesystem only. Reads `global/project-templates/*.md`, `<HOME>/.claude.json`, `<cwd>/.mcp.json`. Writes `<new project>/...` (template files), `<new project>/.claude/{skills,hooks,settings.local.json}`, `<new project>/.mcp.json`, `<new project>/.gitignore`, `<new project>/CLAUDE.md`. Temporary tarball extraction under `tempfile.mkdtemp()`.
**Testing**: pytest (already in dev-deps via `setup/pyproject.toml` if present; otherwise the existing smoketest pattern `setup/tools/_smoketest.py` and a new lightweight harness under `tests/` that imports cabal modules headlessly). Textual's `app.run_test()` for screen-level interaction tests on `InitProjectScreen` and `ProjectMcpScreen`.
**Target Platform**: Windows 10/11 (primary — user's machine), macOS, Linux. Path-conversion shim (`MSYS_NO_PATHCONV=1`) required when running under Git Bash on Windows.
**Project Type**: Desktop TUI (Textual `App` packaged as PyPI console script `cabal` + PyInstaller `.exe`).
**Performance Goals**: SC-7 — Init flow with a < 5 MB template tarball completes the file-injection step in < 10 s on a typical dev laptop, excluding the `claude -p` invocation (which has no time budget — it's interactive AI). UI MUST not block the event loop during any shell-out.
**Constraints**: No new runtime pip dependency (NFR-4). All long-running ops dispatched via `run_worker(..., thread=True)`. Tarball extraction must reject absolute paths and `..` segments (R-5). Project name validated against POSIX-safe + Windows-reserved-name list (R-8).
**Scale/Scope**: Part A — ~12 screen modules + ~24 installer modules + 8 helper modules already in place. Part B — 2 new screens + 1 helper + 1 prompt module + ~50 lines of changes to `home.py` and `app.py`. Expected new code: < 1000 lines total.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0, the following gates apply:

- **Gate 1 — Spec-First Conformance**: `N/A — no external protocol`. The feature shells out to `gh` and `claude` CLIs (their own UX is the contract surface, not a spec we implement), reads/writes `.mcp.json` (a Claude Code config file — the schema is observed, not standardised by an RFC), and uses GitHub's tarball download endpoint via `gh api` (gh handles auth and shape). No new protocol implementation, no conformance scope to publish.
- **Gate 2 — Subagent Delegation**: ✅ — see Subagent Delegation table below. Every phase has an owner from `.specify/memory/agents.md` (Python work → `@python-architect` + `@python-tester`; verification → `@code-plan-verifier`; orchestration glue → `main`).
- **Gate 3 — Contract Tests Before Implementation**: `N/A — no protocol surfaces`. We do not expose an API. Internal CLI invocations (`gh`, `claude`) are validated by integration tests in `tests/integration/` that assert on the call shape (subprocess args) using `subprocess.run` patched via `pytest-monkeypatch`, but those are not "contract tests" in the constitutional sense (Gate 3 is binding on protocol surfaces only — see Principle III).
- **Gate 4 — Reversible Config Changes**: `N/A — no global/ writes`. Part B reads `global/project-templates/*.md` (existing) and `global/git/` (existing) but writes only to user-selected project folders (which are outside this repo). No change to `~/.claude/` happens from the Init Project flow — that remains `LocalScreen`'s job for the user's prompt-lib repo itself. Part A is a pure code refactor under `setup/src/cabal/` — also no `global/` writes. Rollback = `git revert` the feature branch.
- **Gate 5 — Minimal Skill & Agent Surface**: `N/A — no new skill or agent`. We are adding screens to an existing TUI (`cabal`), not adding `/<command>` skills under `global/skills/` or `@<agent>` definitions under `global/agents/`. The wizard's "invoke claude" step uses the user's already-installed `claude` CLI with whatever skills/agents they already have configured globally + the ones we just wrote into the new project's `.claude/`.
- **Gate 6 — Parallel Isolation**: `N/A`. The Parallel Execution Map below is empty — every phase dispatches at most one writing agent at a time (sequential dispatch). The work is small enough (< 1000 LoC, all in one Python package) that the coordination overhead of parallel agents on worktrees outweighs the wall-clock gain.

All gates pass — no Complexity Tracking entries needed.

## Subagent Delegation

*GATE: References `.specify/memory/agents.md` v2026-05-10.*

| Phase / concern | Owner | Why |
|---|---|---|
| Part A — finishing the wizard.py facade + module-cap audit (FR-1 … FR-6) | `@python-architect` | Python structure decision; the refactor is already 90% landed but needs facade re-export audit + line-cap sweep. |
| Part A — verifying smoketest + PyInstaller (SC-3, SC-5) | `@python-tester` | pytest-style integration test that the smoketest stays byte-identical and that the built `.exe` boots. |
| Part B — `InitProjectScreen` + `ProjectMcpScreen` design (FR-7 … FR-15) | `@python-architect` | Textual screen composition, worker-thread dispatch, fallback paths, file-injection model. |
| Part B — `cabal/gh_templates.py` GitHub template fetcher (FR-9, FR-11) | `@python-architect` | subprocess shape for `gh repo list`, tarball download via `gh api`, safe-extract logic. |
| Part B — `claude -p` invocation helper (FR-14, FR-15, R-7) | `@python-architect` | Subprocess wrapper, MSYS_NO_PATHCONV shim, worker dispatch, error surfacing. |
| Part B — `init_project_prompt.py` prompt template (FR-14) | `main` | Cross-cutting — the prompt names skills/agents from `global/` and is the bridge between the wizard and Claude itself; orchestration concern. |
| Part B — `ClaudeStatsPanel` widget + home-screen mount (FR-16, US11) | `@python-architect` | Textual widget composition + `claude -p "/status"` parsing + `~/.claude.json` fallback. |
| Part B — integration tests for Init flow (SC-7, SC-8, SC-9, SC-10, SC-11) | `@python-tester` | Real subprocess for `gh` (mocked when offline) + real `claude` invocation (mocked when not on PATH); Textual `app.run_test()` driver. |
| `cabal/views/home.py` rewire (FR-7) + `cabal/app.py` PyInstaller-discoverable imports | `@python-architect` | Minimal mechanical change; one Python expert. |
| `GITIGNORE_BY_TEMPLATE` preset update (`.mcp.json` line) in `cabal/views/folder_browser.py` (FR-17) | `@python-architect` | Single mechanical edit across 6 presets + idempotent-append helper in `init_project_service.py`. |
| Plan/spec compliance audit before merge | `@code-plan-verifier` | Gate the merge — read-only audit that no new module exceeded the 500-line cap, that `claude` fallback path actually exists in the code, and that the smoketest still passes. |
| Spec extension, plan/research/data-model/contracts authorship, CLAUDE.md sync | `main` | Cross-domain orchestration — spec-kit artifacts. |

### Parallel Execution Map

*GATE 6: Required when ≥2 writing subagents run concurrently in any phase. Otherwise write `N/A`.*

`N/A` — every phase dispatches at most one writing agent at a time. The work is a single Python package; concurrent writers would race on `cabal/views/home.py` and `cabal/app.py` (both touched by Part B). Sequential dispatch is correct.

## Project Structure

### Documentation (this feature)

```text
specs/005-cabal-tools-polish/
├── plan.md                 # This file (/speckit-plan command output)
├── spec.md                 # Feature specification (already exists, extended 2026-05-28)
├── research.md             # Phase 0 output
├── data-model.md           # Phase 1 output
├── quickstart.md           # Phase 1 output (manual test walkthrough)
├── contracts/
│   ├── gh-cli.md           # `gh repo list`, `gh api repos/<o>/<r>/tarball/<b>` shapes used
│   ├── claude-cli.md       # `claude -p` / `claude --print` invocation shape
│   └── mcp-json.md         # `<project>/.mcp.json` schema observed from Claude Code
└── tasks.md                # Phase 2 output (/speckit-tasks command — NOT created here)
```

### Source Code (repository root)

```text
setup/src/cabal/
├── __init__.py
├── __main__.py                       # entry: `from cabal.wizard import run` (FR-6)
├── wizard.py                         # FACADE — re-exports for smoketest/PyInstaller (FR-1)
├── _paths.py                         # path resolution (frozen exe vs wheel vs source)
├── app.py                            # CabalApp (textual App) — Part A; imports new screens for PyInstaller
├── app_widgets.py                    # AppHeader, AppCommandsProvider
├── banner.py                         # HexBanner + render_banner
├── components.py                     # COMPONENTS, Component, ENV_DESCRIPTIONS, FileStatus
├── diff_apply.py                     # diff_component, apply_statuses, backup_settings, prune_backups
├── env_detect.py                     # detect_env, find_env_vars
├── env_summary.py                    # render_env_summary
├── git_config.py                     # apply_git_line_endings, recommended_autocrlf
├── mcp_ops.py                        # claude_mcp_*, enumerate_mcp_servers, _run_claude_cli
├── tools.py                          # TOOLS, Tool, _installer_for, version-floor helpers
├── updates.py                        # check_for_updates, do_git_pull
├── settings_helpers.py
├── os_filters.py
├── diff_apply.py
├── claude_cli.py                     # NEW (Part B) — extracted `_run_claude_cli` + `claude_print`
├── gh_templates.py                   # NEW (Part B) — list/fetch GitHub template repos
├── init_project_service.py           # NEW (Part B) — InjectableFile staging, safe-extract, write
├── installers/                       # one module per installer group (already in place)
│   ├── __init__.py
│   ├── _common.py
│   ├── ai_clis.py · cdt.py · claude_cli.py · cloud.py · containers.py
│   ├── databases.py · editors.py · gh.py · runtimes.py · specify.py
│   ├── uv.py · vcs.py
├── views/                            # one module per screen
│   ├── __init__.py
│   ├── home.py                       # MODIFIED (Part B) — adds Init/Open Project buttons
│   ├── readme.py · env.py · git_config.py · github_repos.py · global_env.py
│   ├── operations.py · update.py · restore.py · mcp.py
│   ├── gh_device.py · folder_browser.py · local.py · tools.py
│   ├── init_project.py               # NEW (Part B) — InitProjectScreen (FR-8)
│   ├── init_project_prompt.py        # NEW (Part B) — prompt template builder (FR-14)
│   └── project_mcp.py                # NEW (Part B) — ProjectMcpScreen (FR-12)
└── widgets/
    ├── __init__.py
    ├── env_panel.py
    ├── update_panel.py
    └── claude_stats_panel.py         # NEW (Part B) — account type, plan usage, active model (FR-16)

tests/                                # NEW — first test suite for cabal
├── conftest.py                       # textual app fixture, temp project-dir fixture
├── unit/
│   ├── test_gh_templates.py          # parses `gh repo list --json` output, filters isTemplate
│   ├── test_init_project_service.py  # safe-extract refuses absolute paths and `..` segments
│   ├── test_claude_cli.py            # builds correct argv, MSYS shim applied on Windows
│   └── test_facade_reexports.py      # every name from setup/tools/_smoketest.py resolves on cabal.wizard
└── integration/
    ├── test_init_project_screen.py   # Textual run_test() drives the screen end-to-end (gh mocked)
    ├── test_project_mcp_screen.py    # toggle writes to .mcp.json; user/plugin rows are read-only
    └── test_claude_stats_panel.py    # claude /status parser; ~/.claude.json fallback; never leaks tokens

setup/tools/
└── _smoketest.py                     # unchanged — must keep passing (SC-3)

setup/build/
├── cabal.spec                        # PyInstaller — may need hiddenimports for new modules (FR-1 alt)
└── build_exe.py                      # unchanged
```

**Structure Decision**: Single Python package (`setup/src/cabal`) with stdlib-only Part B additions. Tests live in a new `tests/` directory at repo root; pytest already on the user's machine (used elsewhere). No web frontend, no service split — this is a desktop TUI app. The refactor's module layout (Part A) is the substrate Part B builds on: every new file falls into an existing dir (`views/`, root-level helper module, or a sibling test file).

## Complexity Tracking

> No constitution-gate violations to track. The Init Project flow adds 3 new modules + 2 new screens + ~50 lines of edits to existing screens — within the line-cap soft limit (FR-2) for every new file. No skill/agent additions (Gate 5 N/A). No global/ writes (Gate 4 N/A). No parallel writers (Gate 6 N/A). No external protocol (Gate 1 N/A). No contract surfaces (Gate 3 N/A).
