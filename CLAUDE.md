# prompt-lib

Personal Claude Code configuration library — versioned source for agents, hooks, skills, rules, output styles, and settings that power the global Claude Code setup across all projects on this machine.

## What this repo is

Not an application. It is the source of truth for everything in `~/.claude/`. Edit here, deploy with the apply script, restart Claude Code.

## Structure

```
global/                         ← deploy target: ~/.claude/
├── settings.json               ← MCP servers, hooks, theme, model
├── CLAUDE.md                   ← global behavioral instructions (always loaded)
├── design.md                   ← design system preferences (imported by CLAUDE.md)
├── MCP.md                      ← MCP server documentation
├── scripts/
│   └── apply-global-claude-settings.sh
├── agents/                     ← subagent definitions
├── hooks/                      ← SessionStart / PreToolUse / PostToolUse / Stop scripts
├── skills/                     ← slash command definitions
├── rules/                      ← file-pattern-conditional rules (loaded only when paths match)
├── output-styles/              ← response formatting profiles
└── project-templates/          ← CLAUDE.md templates used by @init-project

.claude/                        ← project-local config (not deployed globally)
├── commands/                   ← project slash commands
├── skills/                     ← project skill overrides
└── settings.json               ← project-level settings
```

## Key workflows

After editing anything in `global/`, deploy and restart:

```bash
# Recommended — interactive TUI wizard (preview, doctor, restore, env init, local setup)
python setup/settings-configurator-ui.py

# Fallback — non-interactive bash script
bash setup/tools/apply-global-claude-settings.sh
```

See `setup/README.md` for the wizard's structure and modes.

- **Add a skill:** `global/skills/<name>.md` → apply → available as `/<name>`
- **Add an agent:** `global/agents/<name>.md` → apply → available as `@<name>`
- **Change MCP servers:** edit `global/settings.json` → apply → update `global/MCP.md`
- **Change hooks:** edit `global/hooks/<name>` → apply

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

<!-- SPECKIT START -->
Active spec-kit feature: **005-cabal-tools-polish** — Part A: Refactor `cabal/wizard.py` into maintainable modules. Part B (extended 2026-05-28): Add Init Project wizard view + Project MCP screen + Claude Stats panel.
For technical context, structure, stack decisions, and constitution gate status, read [`specs/005-cabal-tools-polish/plan.md`](specs/005-cabal-tools-polish/plan.md). The full design tree is at `specs/005-cabal-tools-polish/` (spec, plan, research, data-model, contracts, quickstart).

Previously shipped: `004-github-plugin` (Installable Claude Code Plugin v1) at `specs/004-github-plugin/`. `003-issue-triage` (GitHub Issue Triage Orchestrator v1) at `specs/003-issue-triage/`. `002-agent-orchestrator` (Agent Orchestrator — GitHub PR Review v1) at `specs/002-agent-orchestrator/`. `001-a2a-bridge` (A2A Bridge for Multi-Agent CLI Delegation v1) at `specs/001-a2a-bridge/`.
<!-- SPECKIT END -->
