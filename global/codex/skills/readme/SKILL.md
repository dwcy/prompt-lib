---
name: readme
description: Keep the top-level README.md in sync with the live repo state. Use whenever skills, agents, hooks, MCP servers, statusline segments, slash commands, or plugins are added, removed, or renamed; or when the user says "update the readme", "is the readme current", "readme drift", "what's stale in the readme", or asks to document a new feature in the main README. Compares declared README content against the source-of-truth files on disk, flags stale or missing entries, and proposes surgical edits — never full rewrites.
allowed-tools: Read, Edit, Glob, Grep, Bash
---

You are keeping the top-level `README.md` of this repo in sync with what actually exists on disk. The README is a public-facing summary — every table row, link, count, and ASCII preview must reflect current reality.

## Rules

- **Surgical patches only.** Use `Edit` with specific old_string → new_string. Never `Write` a fresh README. Never reformat lines you weren't asked to change.
- **One source of truth per claim.** If the README says "14 specialist subagents", count files in `global/agents/`. If it lists a slash command, the linked source file must exist.
- **Surface drift, don't silently fix everything.** Report drift as a numbered list. Ask which items to patch before editing — unless the user explicitly said "just fix all drift".
- **Preserve existing tone and structure.** Match the README's voice (concise, table-heavy, links to `src` and `docs`). Don't add prose sections that didn't exist.
- **New content goes in the right existing section** — a new slash command goes in the matching sub-table under `## Slash commands`. Only create a new H2 when the user explicitly asks.

## Workflow

### 1 — Scope

If invoked without context, ask: "Full drift audit, or documenting a specific change?"

- **Full audit:** walk every section listed below and verify against the filesystem.
- **Targeted update:** the user names a feature ("I added a statusline segment" / "added a new agent") — jump to the matching section.

### 2 — Detect drift

For each in-scope section, run the checks in the table below. Read the actual files (don't trust memory).

| README section | What to verify |
|---|---|
| `## Functionality` | Count `global/agents/*.md` vs the "N specialist subagents" claim. Count skills (`*.md` at top of `global/skills/` plus any `*/SKILL.md` folder skills) vs "N slash-command skills". MCP servers list matches `global/settings.json → mcpServers` keys. Hook descriptions match `global/settings.json → hooks` + `global/hooks/` files. |
| `## Statusline` | Every `seg_*` referenced in the `row1` / `row2` lists at the bottom of `global/statusline.py` has a corresponding row in either the Row 1 or Row 2 table. Hook references (`global/hooks/post_tool_use.py`, `check_claude_update.py`, etc.) exist. State file paths (`~/.claude/.session_state.json`, `~/.claude/.update_state.json`) match what the script uses. |
| `## Slash commands` sub-tables | Every `[src](...)` link resolves (`global/skills/<name>.md`, `global/skills/<name>/SKILL.md`, `.claude/commands/<name>.md`, `.agents/skills/<name>.md`). Every `[docs](docs/<file>.md...)` link's file exists (anchors not checked). If a skill file exists on disk but no table row mentions it, propose adding a row. |
| `## Layout` | Every path in the ASCII tree exists. The tree is intentionally selective — don't enforce listing everything. |
| `## Apply changes` + plugin install paragraph | `python setup/settings-configurator-ui.py` and `bash setup/tools/apply-global-claude-settings.sh` paths exist. |
| `## Further reading` | Every `[docs/<file>]` link resolves. List broken links as drift. |

### 3 — Report

Output a numbered drift report:

```
README drift found:

1. Functionality table says "14 specialist subagents" — actual count is 16
   → global/agents/*.md = 16 files
2. Slash commands → Git workflow lists /git-foo (line 89) — file missing
   → global/skills/git-foo.md does not exist
3. Statusline → Row 1 table missing the ⬆ <version> segment
   → seg_update is in row1 list of global/statusline.py:N
4. Further reading link [docs/foo.md] is broken
   → file not found

Apply which? [1-4 / all / none]
```

If nothing is stale, say so in one line and stop.

### 4 — Patch

For each item the user approves, use `Edit` with the minimum old_string → new_string. After every patch, re-run the relevant check to confirm the drift is gone.

### 5 — Verify

List patches applied and any items skipped. Don't re-narrate the README — the user can read it.

## When NOT this skill

- Generating a `/docs/` folder for a new project → use `/docs`.
- In-depth architecture, decision records, or workflow walkthroughs → those belong in `docs/*.md`, not the README.
- Release notes / changelogs → out of scope.
- Other READMEs (`global/README.md`, `setup/README.md`, `services/*/README.md`) → mention drift but defer to the user; this skill only owns the top-level `README.md`.
