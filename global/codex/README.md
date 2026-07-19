# prompt-lib for Codex

Codex assets generated from the Claude-oriented prompt-lib library.

## What This Installs

- `skills/` -> copied to `~/.codex/skills/`
- `prompt-lib/references/` -> copied to `~/.codex/prompt-lib/references/`
- `prompt-lib/project-templates/` -> copied to `~/.codex/prompt-lib/project-templates/`
- `prompt-lib/statusline-segments.json` -> native Codex statusline item catalog
- `prompt-lib/conversion-manifest.json` -> copied for auditability

The Cabal Codex panel intentionally avoids Codex auth, session logs, plugin cache,
and SQLite state. Cabal's Statusline screen narrowly manages only
`[tui].status_line` and `[tui].status_line_use_colors` in `config.toml`, preserving
all other Codex settings.

## Project Setup

Use the Local Codex Config panel to scaffold:

- `.agents/skills/`
- `AGENTS.md`

Codex reads project instructions from `AGENTS.md` in this repo style. Claude
continues to use `CLAUDE.md`.

## Conversion Model

- Claude slash skills become Codex folder skills with `SKILL.md`.
- Claude subagents become `role-*` skills. They are role prompts, not separate
  persistent subagent runtimes.
- Rules and output styles become references that Codex can read when useful.
- Claude hooks, MCP/plugin settings, and keybindings are documented as unsupported
  runtime features. Claude's statusline script is not copied; Cabal configures
  Codex's native statusline instead.

Use the Conversion Diff panel to inspect every converted, skipped, or unsupported
source and compare Claude source files with Codex outputs.
