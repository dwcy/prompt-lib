# prompt-lib OpenCode assets

OpenCode-compatible assets generated and curated from this repository's
`global/` and `global/codex/` configuration.

Managed targets:

- `opencode.json` -> `~/.config/opencode/opencode.json`
- `tui.json` -> `~/.config/opencode/tui.json`
- `tools/` -> `~/.config/opencode/tools/`
- compatible skills from `global/codex/skills/` -> `~/.config/opencode/skills/`
- compatible references from `global/codex/references/` -> `~/.config/opencode/prompt-lib/references/`

Claude-only runtime pieces such as hooks, statusline commands, and Claude
settings are not activated in OpenCode. They remain reference material.
