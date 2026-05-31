# Feature Specification: Cabal Tools Polish — Refactor + Init Project Wizard

**Feature ID**: 005-cabal-tools-polish
**Status**: Draft (extended 2026-05-28 with Init Project + Project MCP scope)
**Date**: 2026-05-28
**Branch**: `005-cabal-tools-polish`

This spec covers two related cabal-wizard improvements:

1. **Part A — Refactor** `setup/src/cabal/wizard.py` from one 4500-line file into a package of cohesive modules (already mostly landed on this branch: `setup/src/cabal/views/`, `widgets/`, `installers/`, and helper modules are extracted; `wizard.py` is now 196 lines).
2. **Part B — Init Project wizard view** (new): a home-screen entry point that scaffolds a brand-new project folder, applies a chosen template (GitHub template repo OR one of the local `global/project-templates/*.md`), edits per-project MCP, previews every file that will be written, and finally invokes the `claude` CLI to apply the architecture template against the freshly created `.claude/`.

Both parts share the same module layout from Part A and the same testing/build gates.

## Problem

`setup/src/cabal/wizard.py` has grown to **4502 lines** in a single file. It contains:

- Resource/path resolution (frozen exe vs wheel vs source checkout)
- Banner rendering + the `HexBanner` widget
- ~30 OS detection / env-probe helpers and `detect_env()`
- The `Component` dataclass + `COMPONENTS` registry + `ENV_DESCRIPTIONS` table
- Diff / apply / backup logic for the global → `~/.claude/` deploy
- MCP server enumeration + `claude mcp` CLI wrappers
- GitHub release fetcher + downloader
- ~24 per-tool installers (Node, pnpm, bun, Python, .NET, Docker, Podman, kubectl, Terraform, az, gcloud, aws, gh, claude-cli, claude-devtools, specify, uv, gemini, codex, opencode, grok, cursor, windsurf, copilot, antigravity, ollama, vscode)
- The `Tool` dataclass + `TOOLS` registry + version-floor / outdated detection
- 2 widgets (`EnvPanel`, `UpdatePanel`)
- 17 screens (`HomeScreen`, `ReadmeScreen`, `EnvScreen`, `GitConfigScreen`, `GitHubReposScreen`, `GlobalEnvScreen`, `OperationsScreen`, `UpdateScreen`, `DoctorScreen`, `RestoreScreen`, `McpScreen`, `GhDeviceFlowScreen`, `FolderBrowserScreen`, `LocalScreen`, `ToolsScreen`) plus `AppCommandsProvider` / `AppHeader`
- `CabalApp` (the Textual `App` subclass) + the CSS blob + `main()` / `run()` entry points

A single-file Textual app at this size is hostile to maintenance:

- New screens or installers force scrolling through thousands of unrelated lines.
- Test-time imports pay the cost of loading every Textual widget even when only `detect_env()` or `diff_component()` is needed (the smoketest already does this).
- Git blame / churn signals are smeared across one file — every concurrent edit collides on `wizard.py`.
- Cyclomatic boundaries are invisible: a function in the "installers" section can quietly reach into a screen, or vice versa, with no import-time signal.

## Goal

**Part A** — Split `wizard.py` into a package of cohesive modules without changing observable behavior, the PyPI/PyInstaller/dev-shim entry points, or the public import surface that existing callers depend on.

**Part B** — Give the cabal home screen a first-class **Init Project** path so a user can:

- Pick a parent folder (existing `FolderBrowserScreen`).
- Type a project name.
- Pick a template — either one of the user's **GitHub template repos** (via `gh repo list --json isTemplate`) or one of the **local templates** under `global/project-templates/*.md` (the same set already used by `LocalScreen`).
- Optionally edit the **project-scoped MCP** (`<project>/.mcp.json`) in a view that mirrors `McpScreen` but marks `plugin` and `user` rows read-only.
- Preview every file the wizard will inject (the resolved set from the selected template plus any local scaffolding).
- Apply — which (a) writes the files, then (b) shells out to `claude -p "<prompt>"` from inside the new project so Claude follows the chosen architecture template against the freshly created `.claude/`.

The existing "do things to an existing project" flow (`LocalScreen`) stays — Part B adds the new flow alongside it.

## User Stories

### US1 — Maintainer adds a new tool installer

As a maintainer of `cabal`, I can add support for a new CLI tool (e.g. `bun`, `terraform`) by creating one focused module under `cabal.installers.*` and registering it, without scrolling through ~4500 lines of unrelated screens, widgets, and helpers.

### US2 — Maintainer adds a new screen

As a maintainer, I can add a new Textual screen by creating one file under `cabal.views.*` and importing it where the navigation graph wires screens. The new file does not need to live next to env-probing helpers or `claude mcp` CLI shims.

### US3 — Smoketest stays fast

The existing smoketest (`setup/tools/_smoketest.py`) imports `cabal.wizard` and accesses `COMPONENTS`, `detect_env`, `find_env_vars`, `diff_component`, `GLOBAL_DIR`. After the refactor, those names must still resolve via `from cabal import wizard as m` and `m.<name>` — no caller breaks.

### US4 — Installed `cabal` console script keeps working

`cabal` (PyPI console script), `python -m cabal`, `python setup/settings-configurator-ui.py`, and the PyInstaller `.exe` all enter through `cabal.__main__:main → cabal.wizard.run`. That chain MUST keep working unchanged.

### US5 — PyInstaller build still produces a working binary

The build (`setup/build/cabal.spec` + `setup/build/build_exe.py`) currently lists `cabal.wizard` as the only first-party `hiddenimport`. The refactor must either (a) keep all symbols reachable from `cabal.wizard` so PyInstaller's analyzer pulls them transitively, or (b) extend `hiddenimports` with the new module names. Either is acceptable as long as the built `.exe` boots into the same TUI.

### US6 — User initialises a new project from the wizard home

As a user opening `cabal` in a fresh terminal, the home screen offers two equally prominent paths:

- **Init new project** — opens the new `InitProjectScreen` (Part B).
- **Open existing project** — opens `FolderBrowserScreen`, and on selection pushes the existing `LocalScreen` pre-pointed at that folder.

Both paths reach a project that ends up with `.claude/` configured.

### US7 — User picks a GitHub template repo

On `InitProjectScreen`, after picking the parent folder and project name, the user sees a list of their own GitHub template repos (repos where `isTemplate == true`, fetched via `gh repo list --json isTemplate,name,description,defaultBranchRef,url`). Picking one stages every file in that repo as an "injectable file" the user can review.

If `gh` is not authenticated, or the user has no template repos, or the user explicitly chooses **"No GitHub template"**, the wizard falls back to the **local templates** under `global/project-templates/*.md` (the same list `LocalScreen` already uses). Default selection in that fallback is "apply everything": all files from the picked local template plus the existing `.claude/` scaffolding (skills/, hooks/, settings.local.json stub).

### US8 — User reviews and edits Project MCP before commit

A **Project MCP** view (sibling to `McpScreen`) shows all MCP scopes (`plugin`, `user`, `local`, `project`, `template`) but only allows toggling rows that resolve to **project scope** — they write to `<new-project>/.mcp.json`. Plugin and user rows are displayed read-only with a `(global, not editable here)` hint. The user picks which MCP servers should be wired into the new project before it ships.

### US9 — User reviews every file the wizard will inject

Before committing, the user sees a table of every file the Init flow will write into the new project: source path (template repo or local template), destination relative path, status (`NEW` / `OVERWRITE` / `SKIP`), and a checkbox per row. The user can uncheck rows. Default = all checked. Total file count and total byte count are shown.

### US11 — User sees Claude account type + plan stats on the home screen

As a user opening `cabal`, the home screen shows a second nested panel **next to** the existing `EnvPanel` (which lists installed tools). The new `ClaudeStatsPanel` shows:

- **Account type**: `Pro` / `Max 5x` / `Max 20x` / `Team` / `Enterprise` / `API` / `unknown`.
- **Signed-in identity**: `<email>` or `not signed in — run claude /login`.
- **Plan usage**: 5-hour message budget, weekly cap %, current model — best-effort parse of `claude /status`. On parse failure, render the raw output verbatim with a `[dim]could not parse — raw output below[/dim]` hint.
- **Auth state**: token present / not present (never the value).
- **Refresh**: `Ctrl+S` or a `[Refresh]` button. Initial load on `on_mount` runs on a worker thread.

Render rules:

- Never print an API key, OAuth token, or refresh token.
- If `claude` is not on PATH, show `claude CLI not installed — see Tools screen` and read account hints from `~/.claude.json["oauthAccount"]["emailAddress"]` if it exists, otherwise show "unknown".
- Panel MUST not block the TUI event loop — all shell-outs go through `run_worker(..., thread=True)`.

### US10 — User triggers Claude CLI to apply the architecture template

On Apply, the wizard:

1. Creates `<parent>/<project-name>/` (refuses if it already exists and is non-empty).
2. Writes every checked file from the template + the `.claude/` scaffolding + `.mcp.json` if any project-scope MCP was toggled on.
3. Calls `claude -p "<prompt derived from the chosen template>"` non-interactively (or `claude --print` depending on the installed version), with `cwd = <new project>`, so Claude continues setting up the project against the freshly written `.claude/` (skills, agents, CLAUDE.md, settings.local.json).
4. Streams the `claude` stdout into the status pane and exits back to the home screen on completion.

The wizard MUST NOT block the TUI event loop while `claude` runs — it dispatches via `run_worker(..., thread=True)` like the existing long-running operations (`enumerate_mcp_servers`, `_gh_repos`).

## Out of Scope

**Part A (Refactor)**:

- Behavior changes to any wizard screen, installer, or env probe.
- Renaming public symbols (`detect_env`, `diff_component`, `COMPONENTS`, `GLOBAL_DIR`, `run`, etc.).
- New skills, new agents, new MCP servers.
- Changes to `global/` content.
- Changes to `pyproject.toml` package layout (`packages = ["setup/src/cabal"]` stays).
- Rewriting CSS or layout — the `CabalApp.CSS` blob may move to a sibling file, but its content is preserved verbatim.

**Part B (Init Project)**:

- Authoring brand-new project templates inside this repo (we reuse `global/project-templates/` + the user's GitHub template repos).
- Implementing OAuth or any auth flow for GitHub — we rely on the user's already-authenticated `gh` CLI (the existing `GhDeviceFlowScreen` covers re-auth if needed).
- Cloning private template repos requiring SSO when the `gh` token lacks the scope — surface the error, do not work around it.
- Streaming Claude output line-by-line into the TUI with rich formatting — a plain `Static`-driven append is sufficient for v1; a richer log viewer can come later.
- Editing user- or plugin-scope MCP from the Project MCP screen — those remain read-only there (the existing `McpScreen` still owns editing them).
- Background project-tree refresh while Claude is running — Apply is a one-shot then returns to home.

## Functional Requirements

### Part A — Refactor

- **FR-1** — `cabal/wizard.py` becomes a thin facade. Every symbol that the smoketest, PyInstaller spec, or external callers reference today MUST remain importable as `cabal.wizard.<name>`.
- **FR-2** — No module in the new package may exceed ~500 lines (soft cap; widget/screen modules that exceed it must justify it inline).
- **FR-3** — The installer registry (`_installer_for`, the `TOOLS` list) lives in one module that imports every installer; individual installer functions live in `cabal.installers.<group>`.
- **FR-4** — Screens live in `cabal.views.<name>`; widgets live in `cabal.widgets.<name>`. The `CabalApp` class lives in `cabal.app`.
- **FR-5** — The `CabalApp.CSS` blob moves to a sibling resource (`cabal/app_css.py` or `cabal/_data/app.tcss`) only if doing so does not require any pyproject/data-file change. Otherwise it stays inline in `cabal/app.py`.
- **FR-6** — `cabal/__main__.py` keeps the line `from cabal.wizard import run` (or an equivalent path that resolves through `cabal.wizard`).

### Part B — Init Project + Project MCP

- **FR-7** — `HomeScreen` exposes two top-level buttons in a new "Project" section: **"Init new project"** (push `InitProjectScreen`) and **"Open existing project"** (push `FolderBrowserScreen` → `LocalScreen(start_path=picked)`). The existing button row stays.
- **FR-8** — `InitProjectScreen` lives at `cabal/views/init_project.py` and composes (in order): parent-folder picker (reuses `FolderBrowserScreen` via callback like `LocalScreen` does), project-name `Input` (validated against `^[A-Za-z0-9._-]{1,64}$`), template-source `RadioSet` (`github` / `local`), template `OptionList`, "Edit Project MCP…" button, files-to-inject `DataTable` with per-row `Checkbox`, and an Apply button.
- **FR-9** — GitHub template list is fetched via `gh repo list --json isTemplate,name,description,defaultBranchRef,url --limit 200`, filtered to `isTemplate == true`. Failure (`gh` missing, not authed, network error) MUST surface the error in a status pane and let the user fall back to local templates — never crash.
- **FR-10** — Local templates use the existing `global/project-templates/*.md` discovery path (same enumeration as `LocalScreen`). When the user picks a local template, the staged files are: that `.md` (copied to `<project>/CLAUDE.md`), the `.claude/` scaffold (skills/, hooks/, settings.local.json stub), and the matching `.gitignore` preset from `GITIGNORE_BY_TEMPLATE` if a stem match exists.
- **FR-11** — When the user picks a GitHub template, the staged files are: every file in the repo's default-branch archive (downloaded via `gh api repos/<owner>/<repo>/tarball/<branch>` and extracted to a temp dir). The user reviews them in the files-to-inject table and can uncheck any row.
- **FR-12** — `ProjectMcpScreen` lives at `cabal/views/project_mcp.py` and reuses the `enumerate_mcp_servers()` aggregator. Rows are toggleable only when scope is `project` or `template`; rows with `plugin` or `user` in `scopes` render with `(read-only)` and the toggle action is suppressed for them. Toggle writes to `<project>/.mcp.json` (creating it if needed).
- **FR-13** — Apply MUST refuse to proceed if `<parent>/<project-name>/` already exists AND is non-empty. The user gets a clear error and is sent back to the project-name input.
- **FR-14** — Apply runs `claude -p "<prompt>"` (or `claude --print "<prompt>"` for older versions, detected by `--help`) with `cwd=<new project>`, `stdin=None`, `capture_output=True`, dispatched on a worker thread. The prompt template lives at `cabal/views/init_project_prompt.py` and references the chosen template by name and lists the agents/skills present under the new `.claude/`.
- **FR-15** — If `claude` is missing on PATH, Apply MUST still complete the file-injection step and surface a clear message: `"Files written. claude CLI not installed — skipping architecture step. Install from Tools screen."` — never error out the whole flow.
- **FR-17** — Every flow that writes a project-scope `.mcp.json` (`InitProjectScreen` on Apply, and `LocalScreen` if/when it gains MCP toggling) MUST also ensure `.mcp.json` is listed in the project's `.gitignore`. Concretely:
  - The existing `GITIGNORE_BY_TEMPLATE` presets in `cabal/views/folder_browser.py` MUST each gain a `.mcp.json` line (for `python`, `dotnet`, `frontend`, `monorepo`, `unity`, `other`).
  - `InitProjectScreen.action_apply` MUST, after writing `.mcp.json`, append `.mcp.json` to `<project>/.gitignore` if (a) the file does not already exist OR (b) the file exists but does not already match `.mcp.json` on a line by itself. Idempotent — re-running the wizard against the same project does NOT add duplicate lines.
  - This rule applies even when no template-driven `.gitignore` is written (e.g. a GitHub-template flow where the user opted out of the matching local preset). The minimum `.gitignore` content in that case is a one-line file `.mcp.json\n`.
  - Rationale: project-scope `.mcp.json` may carry literal env-var values copied from `os.environ` at the moment a user toggled an entry (data-model invariant I-7). Committing them would leak secrets.
- **FR-16** — `HomeScreen` composes a second nested panel `ClaudeStatsPanel` (new widget `cabal/widgets/claude_stats_panel.py`) immediately after `EnvPanel`. The panel:
  - Runs `claude -p "/status"` on a worker thread at mount and on `Ctrl+S` / `[Refresh]`.
  - Parses account type, signed-in email, 5-hour message usage %, weekly cap %, active model. On parse failure, renders the raw `/status` output verbatim.
  - Falls back to `~/.claude.json` (reads `oauthAccount.emailAddress` and similar fields) when `claude` is not installed.
  - Never prints token / API-key values — only their presence (`✓ token present` / `✗ no token`).
  - Renders inside the existing `home-scroll` container, BEFORE the "Global Claude Settings" section, and styled to match the existing `EnvPanel` (same border, same panel CSS class).

## Non-Functional Requirements

- **NFR-1** — The smoketest (`python setup/tools/_smoketest.py`) MUST pass before and after the refactor with identical printed output (same component counts, same env probe output for an unchanged host).
- **NFR-2** — `python -m cabal` MUST launch the TUI and reach the home screen identically.
- **NFR-3** — `python setup/build/build_exe.py` MUST produce a working binary that opens the same TUI (validated by launching the exe and reaching the home screen — manual check is acceptable).
- **NFR-4** — No new runtime dependency is introduced. No new pip package, no new Textual / Rich version pin. Part B uses only `gh`, `claude`, the Python stdlib (`subprocess`, `tarfile`, `tempfile`, `shutil`, `json`), and modules already imported by other screens.
- **NFR-5** — Git-blame on the new modules must point to this refactor commit only for moves — substantive changes (a renamed function, a new helper) must each have a justifying commit message.
- **NFR-6** — The Init Project screen MUST not block the TUI event loop. Every shell-out (`gh`, `claude`, tar extract) runs on a worker thread; UI updates happen via `call_from_thread`.
- **NFR-7** — The fetched template tarball is extracted into `tempfile.mkdtemp()`, NOT directly into the project folder, so a user cancelling mid-review leaves no partial files on disk. The temp dir is removed on Apply success, on Cancel, and on screen pop.
- **NFR-8** — `claude -p` exit code is surfaced to the user; non-zero is shown as `[yellow]claude exited N — review .claude/ manually[/yellow]` and does NOT delete the project (the user has invested time picking files).

## Success Criteria

### Part A — Refactor

- **SC-1** — `cabal/wizard.py` shrinks to under 200 lines (facade + re-exports only).
- **SC-2** — No new module exceeds 500 lines without an inline justification comment at the top of the file.
- **SC-3** — `python setup/tools/_smoketest.py` prints identical component counts before and after.
- **SC-4** — `python -m cabal` boots to the home screen on Windows (the user's primary platform) and quits cleanly.
- **SC-5** — The PyInstaller build succeeds and the resulting `cabal.exe` reaches the home screen.
- **SC-6** — Every existing symbol referenced from outside `cabal/wizard.py` (smoketest, `__main__`, the dev shim, the PyInstaller spec, the build README) still resolves via `cabal.wizard.<name>`.

### Part B — Init Project + Project MCP

- **SC-7** — From a fresh `cabal` launch on a host with `gh` authenticated and at least one template repo, the user can: pick a parent dir → name the project → pick a GitHub template → review files → Apply → end up with a populated project dir containing the template's files, `.claude/`, and (if claude was on PATH) a Claude-driven first pass against the new tree. End-to-end time excluding the claude call: < 10 s for a < 5 MB template repo.
- **SC-8** — On a host with **no `gh` auth and no internet**, the same flow falls back to local `global/project-templates/*` and completes without errors.
- **SC-9** — The Project MCP screen toggles a project-scope MCP entry → `<project>/.mcp.json` reflects the change → `claude mcp list` (run inside the project after Apply) shows the entry as a project-scope server.
- **SC-10** — When `<parent>/<project-name>/` already exists and is non-empty, Apply refuses with a clear error and the project tree is unchanged.
- **SC-11** — When `claude` is not on PATH, Apply still completes the file-injection step and prints the "skipping architecture step" notice (FR-15).
- **SC-12** — On `cabal` launch with `claude` installed and signed in, `HomeScreen` renders the `ClaudeStatsPanel` within 3 s with the account type and email visible (`claude -p "/status"` returns < 3 s in practice). The panel never contains a literal API key or OAuth token string.
- **SC-13** — On `cabal` launch with `claude` not installed, `HomeScreen` still renders without error; `ClaudeStatsPanel` shows `claude CLI not installed`.
- **SC-14** — After P3 (project MCP toggle), `grep -c '^\.mcp\.json$' <project>/.gitignore == 1` (exactly one entry, not appended twice on re-Apply). After P2 (offline local-template fallback), `.gitignore` likewise contains exactly one `.mcp.json` line even if no MCP was toggled — the line is added unconditionally during Apply.

## Risks

### Part A — Refactor

- **R-1** — Circular imports between screens that push each other (e.g. `HomeScreen → OperationsScreen → ToolsScreen → HomeScreen`). Mitigation: defer cross-screen imports to method bodies; never import a screen at module top level just to construct it lazily.
- **R-2** — PyInstaller's static analyzer not discovering screens that are only referenced via `app.push_screen(SomeScreen())`. Mitigation: import every screen at the top of `cabal/app.py` so the analyzer sees them; verify by inspecting `setup/build/build/cabal/Analysis-00.toc` or by running the built exe.
- **R-3** — Behavior drift introduced by accidentally renaming a parameter or reordering an `if` branch during the move. Mitigation: each module extraction is one commit with no edits other than moving code + fixing imports; verifier (`@code-plan-verifier`) audits before merge.

### Part B — Init Project

- **R-4** — `gh repo list --json isTemplate` semantics differ across `gh` versions; `isTemplate` was added in gh ≥ 2.20. Mitigation: detect at call site — if the field is missing in the response, gracefully degrade to "no GH templates available" and present the local fallback. Document the minimum `gh` version in the cabal Tools screen description.
- **R-5** — Template tarballs may contain platform-specific paths or symlinks the user does not want. Mitigation: extract to a temp dir, show every staged file in the preview table; users can deselect. Refuse to extract entries with absolute paths or `..` segments (zip-slip / tar-slip).
- **R-6** — `claude -p` long-running invocations may exceed reasonable subprocess timeouts. Mitigation: no timeout, but show a "claude is working…" indicator and a Cancel button that sends SIGTERM (Windows: `process.terminate()`); document this behaviour in the help text on the screen.
- **R-7** — Path-conversion issues on Git Bash for the `claude` subprocess (similar to existing `MSYS_NO_PATHCONV=1` already set in `mcp_ops._run_claude_cli`). Mitigation: route the new invocation through the same hardened helper (extract a shared `_run_claude_cli` if needed, or expose it from `cabal.mcp_ops`).
- **R-8** — Project name collisions with OS-reserved names on Windows (`con`, `nul`, `prn`, `aux`, `com1..9`, `lpt1..9`). Mitigation: validate against that list in the project-name `Input` before enabling Apply.
