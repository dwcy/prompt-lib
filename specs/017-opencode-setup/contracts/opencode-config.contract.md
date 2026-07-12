# Contract: OpenCode Config Assets

## Global config

`global/opencode/opencode.json` must be valid JSON and include:

- `$schema`: `https://opencode.ai/config.json`
- `mcp.codex.type`: `local`
- `mcp.codex.command`: command array ending in `mcp-server`
- `permission.codex_*`: `ask`
- `permission.claude-ask`: `ask`
- `permission.gemini-ask`: `ask`
- `permission.antigravity-chat`: `ask`

## Apply behavior

- Existing target JSON keys not present in the source remain unchanged.
- Source keys override target keys only for prompt-lib-managed settings.
- Invalid target JSON is treated as empty and replaced with valid merged JSON.
