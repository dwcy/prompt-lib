# Data Model: Headroom as a Managed Tool

**Feature**: 010-headroom-tool | **Date**: 2026-06-21

No persistent/runtime data store. The "entities" here are static catalog/config records the feature adds to existing structures. Field shapes mirror what already exists in `setup/src/cabal/tools.py` and `setup/mcp-templates.json`.

## Entity: Featured tool entry (`Tool`)
Added as one element of the `TOOLS` list in `setup/src/cabal/tools.py` (existing `@dataclass Tool`).

| Field | Value for Headroom | Notes |
|---|---|---|
| `key` | `"headroom"` | unique within `TOOLS` |
| `name` | `"Headroom (context compression)"` | display label |
| `description` | one–two sentences: compresses tool outputs/logs/RAG/files before the LLM; on-demand compress/retrieve/stats tools; manual, opt-in | no marketing claims |
| `homepage` | `"https://headroom-docs.vercel.app/docs"` | |
| `repo_url` | `"https://github.com/chopratejas/headroom"` | |
| `install` | `headroom_install` | from `installers/headroom.py` |
| `status` | `headroom_status` | from `installers/headroom.py` |

## Entity: Environment installer entry
Added to `ENV_INSTALLERS` and referenced from `ENV_TOOL_GROUPS["MCP"]` in `tools.py`.

| Field | Value |
|---|---|
| key | `"headroom"` |
| label | `"Headroom"` |
| install fn | `headroom_install` |
| group | `"MCP"` (dedicated group for tools that are MCP servers) |

No `WINGET_IDS` entry (not a winget package).

## Entity: Installer functions (`installers/headroom.py`)

| Function | Signature | Behavior |
|---|---|---|
| `headroom_status` | `() -> str` | `"not installed"` if `shutil.which("headroom")` is None; else `"installed {version}"` from `headroom --version` (fallback `"installed"`). |
| `headroom_install` | `() -> tuple[bool, str]` | Ensure `uv` (via `uv_install()`); if `headroom` present → `uv tool upgrade`; else `uv tool install "headroom-ai[<extra>]"`. Returns `(ok, message)`. Extra confirmed in spike. |

## Entity: MCP server template
Added under `templates` in `setup/mcp-templates.json`; consumed by `enumerate_mcp_servers` (visibility) and `claude_mcp_add_from_template` (registration).

| Field | Value | Notes |
|---|---|---|
| `transport` | `"stdio"` | |
| `command` | `"headroom"` | confirm in spike |
| `args` | `["mcp", "serve"]` | confirm in spike |
| `env_required` | `[]` | no secret needed for local stdio server |
| `default_enabled` | `false` | opt-in (FR-006) |

State: appears as scope `"template"` until registered; becomes scope `"user"` + `active` after `claude mcp add -s user`.

## Entity: Research findings document
`specs/010-headroom-tool/research.md` §B — the investigate-only proxy verdict (FR-009). Required terminal field: **Verdict ∈ {pursue, shelve, reject}**, filled during the implementation spike.
