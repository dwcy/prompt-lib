# Config Contract: Headroom `mcp-templates.json` entry

**Feature**: 010-headroom-tool | **Type**: internal config contract (not an external protocol)

This is the only "contract" the feature owns. It is the shape of a `setup/mcp-templates.json` template entry, already enforced by the existing consumers `_load_mcp_templates`, `enumerate_mcp_servers`, and `claude_mcp_add_from_template` in `setup/src/cabal/mcp_ops.py`. No wire/protocol contract tests are required (Constitution Gate 3 = N/A — Headroom owns its MCP tool schemas; we only register the server).

## Entry shape

```json
"headroom": {
  "transport": "stdio",
  "command": "headroom",
  "args": ["mcp", "serve"],
  "env_required": [],
  "default_enabled": false
}
```

## Field rules (as consumed by `mcp_ops.py`)

| Field | Required | Constraint |
|---|---|---|
| `transport` | yes | `"stdio"` here. Non-stdio would add `--transport` in `claude_mcp_add_from_template`; not used. |
| `command` | yes | base executable. On Windows, `pnpm`/`npx`/`bunx` get `cmd /s /c`-wrapped automatically; `headroom` is a direct exe so it is passed through unwrapped. |
| `args` | yes | list of strings appended after `--` in `claude mcp add`. |
| `env_required` | yes (may be empty) | each var must be present in the environment at register time or registration fails with a clear "Missing env var" message. Empty here — local stdio server needs no secret. |
| `default_enabled` | yes | `false` → not auto-registered; opt-in via the cabal MCP manager (FR-006). |

## Behavioral contract (verified by quickstart, not by automated contract tests)

- **Visibility**: with the entry present and not yet registered, `enumerate_mcp_servers()` returns a `headroom` key whose `scopes` includes `"template"`.
- **Registration**: `claude_mcp_add_from_template("headroom", <entry>)` runs `claude mcp add -s user headroom -- headroom mcp serve` (Windows-wrapped as needed) and returns `(True, ...)`.
- **Post-registration**: `claude mcp list` reports `headroom` as Connected; a fresh Claude Code session exposes `headroom_compress`, `headroom_retrieve`, `headroom_stats`.
- **Removal**: `claude mcp remove -s user headroom` (or the cabal manager) cleanly de-registers it.
