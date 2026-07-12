# Data Model: OpenCode Setup

## OpenCodeAsset

- `key`: stable row key for UI and tests
- `label`: human-readable target asset
- `source`: repo file path
- `target`: OpenCode destination path
- `state`: `NEW`, `CHANGED`, or `UNCHANGED`
- `group`: `config`, `tools`, `skills`, `references`, or `docs`

## OpenCodeStatus

- `cli`: OpenCode executable present
- `desktop_app`: OpenCode desktop app present
- `version`: optional CLI version
- `global_config`: `opencode.json` exists
- `tui_config`: `tui.json` exists
- `skills_dir`: global skills directory exists
- `tools_dir`: global tools directory exists
- `codex_cli`: Codex executable present
- `codex_mcp_configured`: OpenCode config has local Codex MCP entry
- `claude_cli`, `gemini_cli`, `antigravity_cli`: bridge CLI availability

## Apply State

- Preview is read-only.
- Apply copies files when missing/changed.
- Apply merges JSON files and preserves unrelated existing keys.
