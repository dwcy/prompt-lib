# prompt-lib

Personal Claude Code configuration library - versioned source for agents, hooks, skills, rules, output styles, and settings that power the global Claude Code setup across all projects on this machine.

## What this repo is

Not an application. It is the source of truth for everything in `~/.claude/`. Edit here, deploy with the apply script, restart Claude Code.

## Structure

```text
global/                         <- deploy target: ~/.claude/
|-- settings.json               <- MCP servers, hooks, theme, model
|-- CLAUDE.md                   <- global behavioral instructions (always loaded)
|-- design.md                   <- design system preferences (imported by CLAUDE.md)
|-- MCP.md                      <- MCP server documentation
|-- scripts/
|   `-- apply-global-claude-settings.sh
|-- agents/                     <- subagent definitions
|-- hooks/                      <- SessionStart / PreToolUse / PostToolUse / Stop scripts
|-- skills/                     <- slash command definitions
|-- rules/                      <- file-pattern-conditional rules (loaded only when paths match)
|-- output-styles/              <- response formatting profiles
`-- project-templates/          <- CLAUDE.md templates used by @init-project

.claude/                        <- project-local config (not deployed globally)
|-- commands/                   <- project slash commands
|-- skills/                     <- project skill overrides
`-- settings.json               <- project-level settings
```

## Key workflows

After editing anything in `global/`, deploy and restart:

```bash
# Recommended - interactive TUI wizard (preview, doctor, restore, env init, local setup)
./run        # POSIX
.\run.cmd    # Windows

# Graphical workspace from the same root launcher
./run web
.\run.cmd web
./run tauri
.\run.cmd tauri

# Direct source fallback
python setup/settings-configurator-ui.py

# Fallback - non-interactive bash script
bash setup/tools/apply-global-claude-settings.sh
```

See `setup/README.md` for the wizard's structure and modes.

- **Add a skill:** `global/skills/<name>.md` -> apply -> available as `/<name>`
- **Add an agent:** `global/agents/<name>.md` -> apply -> available as `@<name>`
- **Change MCP servers:** edit `global/settings.json` -> apply -> update `global/MCP.md`
- **Change hooks:** edit `global/hooks/<name>` -> apply

### One-time per clone

Enable repo git hooks (currently: Textual base-class shadow check):

```bash
git config core.hooksPath .githooks
```

Enable the identity-injection filter (plugin manifests are committed with
`{{LOGGED_IN_EMAIL}}` / `{{GIT_USER_NAME}}` / `{{REPO_URL}}` placeholders; the
filter swaps in the logged-in account email, your git name, and the origin
remote URL on checkout and strips them again on commit, so no personal
identity lands in git):

```bash
git config filter.inject-email.smudge "python setup/tools/email-filter.py smudge"
git config filter.inject-email.clean  "python setup/tools/email-filter.py clean"
git checkout -- .claude-plugin global/.claude-plugin
```

## OKF knowledge catalog

The generated OKF catalog lives under `docs/okf/prompt-lib/` after running the Cabal Knowledge screen export or:

```bash
python -m cabal.okf export --out docs/okf/prompt-lib
python -m cabal.okf doctor docs/okf/prompt-lib --format human
```

Use `docs/okf/README.md` for the human explanation and `docs/okf/prompt-lib/graph.json` for machine-readable agent, skill, hook, rule, template, Codex, output-style, and Spec Kit relations. The bundle is generated reference data, not the source of truth; fix source files first and regenerate.

Claude, Codex, and compatible agents do not automatically ingest this bundle just because it exists. When a task asks about how the agent ecosystem connects, routing overlap, unused concepts, or skill-agent references, explicitly read the OKF docs or graph. SQLite search, preflight, context packs, semantic search, and a usage ledger from `009-okf-analytics-rag` are implemented in the CLI, Cabal's Knowledge screen OKF RAG panel, and the opt-in `okf-rag` stdio MCP server (`cabal-okf-rag`, 8 tools, registered via the wizard's MCP screen or `claude mcp add`).

Convention: only currently in-progress spec-kit features belong between the markers below. When a feature fully merges, remove its entry instead of appending a "recently merged" / "previously active" / "shipped" line — the full record already lives permanently in that feature's own `specs/<n>-name/plan.md`, so restating it here would just be a second, always-loaded copy of the same history. Update entries in place; don't accumulate a changelog.

<!-- SPECKIT START -->
Active spec-kit feature: **015-web-ui-overhaul** — Replace the read-only 011 web UI with a full-parity desktop workspace covering all 22 cabal feature modules, including confirmation-guarded mutations (prepare/execute tickets with precondition digests, SSE job streams, SQLite jobs + audit). Shared Python service layer feeds both the TUI and a new FastAPI backend (`setup/src/cabal/webapi/`); frontend is Vite + React + TS (pnpm) in `apps/cabal-desktop/`, wrapped in a Tauri v2 shell (sidecar backend, single-instance, window-state — Tauri mandated, not Electron). Legacy `cabal/web/` retires at parity. Read [`specs/015-web-ui-overhaul/plan.md`](specs/015-web-ui-overhaul/plan.md); full design tree at `specs/015-web-ui-overhaul/` (spec, plan, research, data-model, contracts, quickstart).

Also active: **009-okf-analytics-rag** - OKF Analytics and RAG Index: SQLite-backed search, preflight, context packs, semantic retrieval, a usage ledger, and the opt-in `okf-rag` stdio MCP server (8 tools via `cabal-okf-rag`) are implemented in the CLI and Cabal's Knowledge screen; optional DuckDB exploration is still outstanding. Design tree at [`specs/009-okf-analytics-rag/plan.md`](specs/009-okf-analytics-rag/plan.md).

Also active: **019-agent-eval-harness** — eval/regression harness for agent configurations: baseline-vs-candidate A/B runs of fixed coding tasks from pinned git refs in throwaway worktrees, N repetitions per cell, evaluated by deterministic checks (tests/build/lint + unrequested-change scope), an LLM pairwise judge (both A/B orders, disagreement → tie), and stream-json agent metrics (tool calls, tokens, wall time), reduced into a per-matrix report. Runner lives in `setup/src/cabal/evals/` (`python -m cabal.evals validate|run|judge|report`); benchmark-as-code under `evals/` (tasks/rubrics/configs versioned, results gitignored); per-run `CLAUDE_CONFIG_DIR` isolation so profiles never touch `~/.claude/`. Claude Code adapter first; Codex/Gemini behind the adapter seam. Read [`specs/019-agent-eval-harness/plan.md`](specs/019-agent-eval-harness/plan.md).

Also active: **018-dotnet-codegen** — fast/cheap LLM code generation pipeline for .NET backends (route → architect → approval gate → write → verify), applying the cost-engineering principles measured by Aider, Cursor, Lovable and Bolt. Pipeline lives in `setup/src/cabal/dotnetgen/` with a thin `/dotnet-codegen` skill as the entry point; three locked architecture templates chosen once per project; per-stage provider routing including local models via Ollama / LM Studio; hard retry ceiling with environment-vs-code-defect classification. Greenfield first (US1–US5); brownfield + Roslyn semantic map gated to Phase B. Existing .NET assets (`@dotnet-architect`, `/dotnet-class`, `csharp.md`) are unmodified and coexist. Read [`specs/018-dotnet-codegen/plan.md`](specs/018-dotnet-codegen/plan.md).

Also active: **021-codegen-eval-modules** — Cabal Desktop modules for the two CLI-only subsystems above (018 dotnetgen, 019 evals), so neither needs a terminal: an approval-gate view that writes nothing before you approve, per-stage cost breakdown, stage→model bindings, eval matrix launch/cancel/resume, the A/B comparison view, and GUI authoring of the benchmark definition tree. Central design constraint: `JobManager` is memory-only and the Tauri shell kills the backend it spawned on exit, so runs execute as **detached OS processes** and the on-disk artifact trees (`.dotnetgen/runs/`, `evals/results/`) are the source of truth — the job record and SSE stream are a live view, not the run. Consequence: reading a workspace-launched run and a CLI-launched run is one code path, and the frontend never computes an aggregate. Both wrapped subsystems stay unmodified; gaps (e.g. `cabal.evals` has no `--json`) are recorded as findings. Backend in `setup/src/cabal/webapi/`, frontend in `apps/cabal-desktop/src/modules/{codegen,evals}/`. Read [`specs/021-codegen-eval-modules/plan.md`](specs/021-codegen-eval-modules/plan.md).

<!-- SPECKIT END -->
