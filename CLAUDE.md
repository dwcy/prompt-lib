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

Claude, Codex, and compatible agents do not automatically ingest this bundle just because it exists. When a task asks about how the agent ecosystem connects, routing overlap, unused concepts, or skill-agent references, explicitly read the OKF docs or graph. SQLite search, preflight, context packs, semantic search, and a usage ledger from `009-okf-analytics-rag` are implemented in the CLI and Cabal's Knowledge screen OKF RAG panel; an `okf-rag` MCP server is still outstanding.

Convention: only currently in-progress spec-kit features belong between the markers below. When a feature fully merges, remove its entry instead of appending a "recently merged" / "previously active" / "shipped" line — the full record already lives permanently in that feature's own `specs/<n>-name/plan.md`, so restating it here would just be a second, always-loaded copy of the same history. Update entries in place; don't accumulate a changelog.

<!-- SPECKIT START -->
Active spec-kit feature: **014-cabal-services-view** — Surface the runnable local agent services (orchestrator, a2a-bridge) as first-class apps in the cabal TUI via a dedicated **Local Agent Services** screen: a service registry, a session-scoped process supervisor (start/stop/live status — net-new for cabal), per-service prerequisite checks with actionable messages, and `uv tool` installers. mcp-bus is NOT shown here (it lives in the Tools **MCP** group as a client-launched stdio MCP server). No `global/` changes, no external protocol. Out of scope: auto-restart supervisor, cross-launch PID persistence.
For technical context, structure, stack decisions, and constitution gate status, read [`specs/014-cabal-services-view/plan.md`](specs/014-cabal-services-view/plan.md). The full design tree is at `specs/014-cabal-services-view/` (spec, plan, research, data-model, contracts, quickstart).

Also active: **009-okf-analytics-rag** - OKF Analytics and RAG Index: SQLite-backed search, preflight, context packs, semantic retrieval, and a usage ledger are implemented in the CLI and Cabal's Knowledge screen; the `okf-rag` MCP server and optional DuckDB exploration are still outstanding. Design tree at [`specs/009-okf-analytics-rag/plan.md`](specs/009-okf-analytics-rag/plan.md).

Also active: **016-install-wizard** — Installable distribution with installation wizard: close the gap between the existing cabal tooling and a true one-command installable — installation manifest (`~/.claude/.cabal/install-manifest.json`), non-interactive CLI (`cabal apply/doctor/uninstall/--version`), manifest-driven uninstall, interrupted-apply detection/resume, and execution of the release-readiness checklist. Release blocker recorded: the PyPI name `cabal` is taken; the rename decision + Trusted Publishing setup are user-owned runbook steps, and no `v*` tag ships with this feature. No `global/` changes, no external protocol. Design tree at [`specs/016-install-wizard/plan.md`](specs/016-install-wizard/plan.md).
<!-- SPECKIT END -->
