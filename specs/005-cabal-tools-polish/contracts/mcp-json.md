# Contract — `<project>/.mcp.json` schema (Part B)

The project-scope MCP file Claude Code reads when launched in a project. Schema observed from current Claude Code behaviour and from `cabal/mcp_ops.py:109-119` which already reads it.

## File location

`<ProjectInitPlan.target_dir>/.mcp.json` — at the project root, NOT inside `.claude/`.

## Schema

```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "<executable>",
      "args": ["<arg1>", "<arg2>", "..."],
      "env": {
        "<ENV_VAR>": "<value>"
      }
    }
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `mcpServers` | `dict[str, ServerEntry]` | yes | Top-level container. Empty `{}` is valid — write the file anyway, since `cabal` having created the file signals intent. |
| `mcpServers.<name>` | `ServerEntry` | yes per entry | One per server toggled on. |
| `mcpServers.<name>.command` | `str` | yes | Executable on PATH. Same shape `claude_mcp_add_from_template` already uses (`cabal/mcp_ops.py:147`). |
| `mcpServers.<name>.args` | `list[str]` | yes | argv tail. Empty list if none. |
| `mcpServers.<name>.env` | `dict[str, str]` | no | Defaults to `{}` if omitted. We always write the key (with at least `{}`). |

## Windows wrapping

For `command` in `{"pnpm", "npx", "bunx"}` on Windows, `cabal/mcp_ops.py:149` already wraps the call:

```json
{
  "command": "cmd",
  "args": ["/s", "/c", "npx -y @upstash/context7-mcp"]
}
```

We MIRROR that wrapping when writing `.mcp.json` so `claude` launches the server identically whether it was added via `claude mcp add -s user` (existing path) or read from `.mcp.json` (new path).

## Round-trip safety

`cabal/mcp_ops.enumerate_mcp_servers()` reads `<cwd>/.mcp.json` and adds entries to scope `project`. After Apply, when the user opens the new project in cabal and lands on `McpScreen`, every entry we wrote MUST show up as scope `project`. Test: `tests/integration/test_project_mcp_screen.py` writes a `.mcp.json` then asserts `enumerate_mcp_servers()` returns the entry with `"project" in scopes`.

## Forbidden contents

- Comments — `.mcp.json` is strict JSON; Claude Code does not parse JSONC.
- `transport` field at write time — we only write `stdio` servers in v1 (the dominant case). HTTP/SSE transports require `--transport` at `claude mcp add` time but are not the priority for project-scoped servers.
- `env_required` field — that's an MCP-template advisory field used by cabal's UI, not part of Claude Code's runtime contract.

## Validation on write

Before writing, the wizard:

1. Computes the JSON via `json.dumps(payload, indent=2, ensure_ascii=False)`.
2. Round-trips it via `json.loads(...)` to assert validity.
3. Writes to a temp file in `<target_dir>`, then `os.replace()` onto `.mcp.json` (atomic on Windows for same-volume rename).
4. Asserts the post-write file passes `json.loads`.

This is paranoia, but `.mcp.json` is the hand-off contract to Claude Code — a corrupt one breaks every subsequent session in that project.

## Gitignore obligation (FR-17)

Every wizard flow that writes `.mcp.json` MUST also ensure the project's `.gitignore` lists `.mcp.json`. Reason: `mcpServers.<name>.env` may contain literal secret values copied verbatim from `os.environ` at toggle time (data-model invariant I-7).

**Algorithm** (idempotent — safe to re-run):

```python
gi = target_dir / ".gitignore"
needle = ".mcp.json"
if not gi.exists():
    gi.write_text(needle + "\n", encoding="utf-8")
else:
    lines = gi.read_text(encoding="utf-8").splitlines()
    if needle not in lines:
        # Append on its own line, after a blank-line separator if the file doesn't already end on one.
        sep = "" if (lines and lines[-1] == "") else "\n"
        with gi.open("a", encoding="utf-8") as f:
            f.write(sep + needle + "\n")
```

**Preset alignment**: every entry of `GITIGNORE_BY_TEMPLATE` in `cabal/views/folder_browser.py` (`python`, `dotnet`, `frontend`, `monorepo`, `unity`, `other`) MUST also include a `.mcp.json` line, so template-driven first-write of `.gitignore` already has the entry — the append step above then becomes a no-op for those flows. This keeps the rule consistent whether the user picked a local template (writes the preset, which already excludes `.mcp.json`) or a GitHub template (no preset, so the append step writes the minimum one-line file).

**What we explicitly do NOT do**:

- We do not add `.claude/settings.local.json` to `.gitignore` — that file lives in `.claude/` and is a separate concern; today, the prompt-lib project itself checks in `.claude/settings.local.json` (mostly safe permissions). Future spec work can revisit.
- We do not run `git rm --cached .mcp.json`. If a prior tooling commit added the file to a repo, that's a pre-existing leak the wizard does not silently rewrite history to fix — but we surface a yellow warning at Apply time: `[yellow].mcp.json was already tracked by git in this repo — run 'git rm --cached .mcp.json' to stop tracking it.[/yellow]` (cheap check via `git ls-files --error-unmatch .mcp.json` exit code).

## Out of scope

- Editing user-scope (`~/.claude.json["mcpServers"]`) or plugin-scope MCP from `ProjectMcpScreen` — those rows are read-only there (FR-12).
- Migrating an existing `.mcp.json` — if the file exists in `target_dir` at Apply time, we surface an error (FR-13: target dir must be empty).
