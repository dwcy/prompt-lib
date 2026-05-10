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
python setup/apply.py

# Fallback — non-interactive bash script
bash setup/tools/apply-global-claude-settings.sh
```

See `setup/README.md` for the wizard's structure and modes.

- **Add a skill:** `global/skills/<name>.md` → apply → available as `/<name>`
- **Add an agent:** `global/agents/<name>.md` → apply → available as `@<name>`
- **Change MCP servers:** edit `global/settings.json` → apply → update `global/MCP.md`
- **Change hooks:** edit `global/hooks/<name>` → apply

<!-- SPECKIT START -->
Active spec-kit feature: **001-a2a-bridge** — A2A Bridge for Multi-Agent CLI Delegation (v1).
For technical context, project structure, stack decisions, and constitution gate status, read [`specs/001-a2a-bridge/plan.md`](specs/001-a2a-bridge/plan.md). The full design tree is at `specs/001-a2a-bridge/` (spec, plan, research, data-model, contracts, quickstart).
<!-- SPECKIT END -->
