# Contract — `.claude-plugin/marketplace.json`

**Spec surface**: Claude Code marketplace manifest (v1, as documented at https://code.claude.com/docs/en/plugin-marketplaces and https://code.claude.com/docs/en/plugins-reference).
**Conformance scope**: This repo's marketplace catalog MUST validate against the published marketplace schema and MUST be loadable via `/plugin marketplace add <owner>/prompt-lib`.

This contract is the wire-format contract for the marketplace file. It is the test surface for Constitution Gate 3.

---

## Required shape

```json
{
  "$schema": "https://json.schemastore.org/claude-code-plugin-marketplace.json",
  "name": "prompt-lib",
  "owner": {
    "name": "Dawid"
  },
  "description": "Personal Claude Code library — skills, agents, hooks, and MCP servers.",
  "plugins": [
    {
      "name": "prompt-lib",
      "source": "./global",
      "description": "Skills, agents, hooks, and MCP servers for Claude Code.",
      "author": { "name": "Dawid" },
      "homepage": "https://github.com/<owner>/prompt-lib",
      "repository": "https://github.com/<owner>/prompt-lib",
      "keywords": ["skills", "agents", "hooks", "mcp", "claude-code"],
      "category": "productivity"
    }
  ]
}
```

Replace `<owner>` with the actual GitHub owner before publishing.

---

## Field-level requirements

| Field | Constraint | Test |
|---|---|---|
| `name` | MUST equal `"prompt-lib"`. MUST be kebab-case. MUST NOT be a reserved name. | `jq .name marketplace.json` → string equality |
| `owner` | MUST be present. `owner.name` MUST be non-empty. | `jq '.owner.name' marketplace.json` → non-empty |
| `plugins` | MUST be an array of length ≥ 1. | `jq '.plugins | length' marketplace.json` → `>= 1` |
| `plugins[*].name` | MUST equal `"prompt-lib"`. MUST equal the `name` in `global/.claude-plugin/plugin.json`. | cross-file equality |
| `plugins[*].source` | MUST be `"./global"` (relative, starts with `./`, no `..`). | `jq '.plugins[0].source' marketplace.json` → `"./global"` |
| `plugins[*].version` | MUST be omitted (commit SHA versioning per research R4). | `jq '.plugins[0] | has("version")' marketplace.json` → `false` |

---

## Forbidden shapes

The following MUST NOT appear:

- `"name": "claude-code-marketplace"` or any other reserved name (see plugin docs reserved list).
- `"source"` containing `..` (path traversal).
- A `metadata` object that conflicts with the top-level `description` / `version`.
- More than one entry in `plugins` for v1 (single-plugin marketplace per research R2).

---

## Validation procedure

1. **Schema check** — `claude plugin validate .` from repo root. MUST exit 0 with no `error` lines. `warning` lines are acceptable only if explicitly noted in this contract.
2. **Cross-file check** — `marketplace.json.plugins[0].name` MUST equal `global/.claude-plugin/plugin.json.name`. A small bash one-liner suffices: `[ "$(jq -r .plugins[0].name .claude-plugin/marketplace.json)" = "$(jq -r .name global/.claude-plugin/plugin.json)" ]`.
3. **Local install dry-run** — `claude --plugin-dir ./global` MUST start without plugin load errors. (`/plugin list` should show `prompt-lib` as loaded.)

---

## Non-blocking warnings expected (and accepted)

- `"Plugin name 'prompt-lib' is not kebab-case"` — should NOT fire (`prompt-lib` IS kebab-case). If it does, contract is violated.
- `"No marketplace description provided"` — MUST NOT fire (description is provided).
- `"Marketplace has no plugins defined"` — MUST NOT fire.

If any of the above fire, that is a contract violation — fix the file, not the contract.
