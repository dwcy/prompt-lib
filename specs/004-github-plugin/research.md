# Phase 0 — Research: prompt-lib as a Claude Code Plugin

**Feature**: 004-github-plugin
**Date**: 2026-05-16
**Spec**: [spec.md](./spec.md)

This document resolves every design unknown the spec raised. Each section is **Decision / Rationale / Alternatives considered**. No `NEEDS CLARIFICATION` remains at the end.

---

## R1. Plugin root location

**Decision**: Use the existing `global/` directory as the plugin root. Add `global/.claude-plugin/plugin.json`, `global/.mcp.json`, and `global/hooks/hooks.json`. The marketplace catalog lives at the repo root in `.claude-plugin/marketplace.json` and references the plugin via the relative source `./global`.

**Rationale**:

- **Single source of truth.** `global/` already contains `skills/`, `agents/`, `output-styles/`, and `hooks/` in the exact layout the plugin model expects. Adding three new files (`plugin.json`, `.mcp.json`, `hooks/hooks.json`) is enough to make it a valid plugin. Both distribution paths read from the same files; no content duplication, no build step.
- **Apply path stays trivial.** The wizard already copies `global/*` to `~/.claude/`. The new plugin-only files (`.claude-plugin/`, plugin-shaped `hooks/hooks.json`, `.mcp.json`) are either harmless in `~/.claude/` or excluded by a small wizard-side ignore list. No structural change.
- **No bandwidth waste in cache.** Marketplace install copies only the `./global` subtree into `~/.claude/plugins/cache/...`, not the entire repo (no `services/`, `specs/`, `setup/`, `.specify/`, `docs/`).

**Alternatives considered**:

- **(A) Plugin at repo root.** Marketplace catalog and plugin manifest both at `/`. Rejected: the whole repo (services, specs, setup, docs) would be copied into the plugin cache on install. The plugin would carry irrelevant 100s of files; `Glob`/`Grep` results inside the cache would be polluted.
- **(B) New `plugin/` subdir, symlinks back to `global/`.** Plugin root at `plugin/`, with `plugin/skills` → `../global/skills` etc. Rejected: per the plugin caching docs, symlinks resolving outside the plugin's own directory are dereferenced (for marketplace installs) or skipped (for `--plugin-dir` installs). The latter breaks local development — the most important contributor workflow.
- **(C) Build step that copies `global/` → `plugin/` pre-commit.** Rejected: introduces a CI/local-script dependency and a window where the plugin is out of sync with `global/`.

---

## R2. Marketplace topology — single-plugin marketplace vs separate repos

**Decision**: One marketplace, one plugin, same repo. `marketplace.json` at `.claude-plugin/marketplace.json` declares marketplace `prompt-lib` with one plugin entry `prompt-lib` sourced as relative path `./global`.

**Rationale**:

- The current prompt-lib is a single, integrated bundle (skills, agents, hooks all reference each other and assume the same MCP servers are present). Splitting it into multiple plugins would manufacture coupling problems that don't exist today.
- A single-plugin marketplace is the documented happy path; the marketplace walkthrough example in the docs is exactly this shape.
- Install command stays short: `/plugin marketplace add <owner>/prompt-lib` then `/plugin install prompt-lib@prompt-lib`.

**Alternatives considered**:

- **Separate `prompt-lib-skills`, `prompt-lib-agents`, `prompt-lib-mcp` plugins** in the same marketplace. Rejected for v1: zero use case for installing only one. Can be refactored later without breaking change if a need emerges.
- **A separate marketplace repo** (e.g. `pawzor/claude-marketplace` listing `pawzor/prompt-lib` as `github` source). Rejected for v1: adds a second repo to maintain. Useful only if multiple plugins from different repos need to be catalogued.

---

## R3. Plugin source type — relative path vs `github`

**Decision**: Use the relative path source `./global` in `marketplace.json`. This works because users add the marketplace via `/plugin marketplace add <owner>/prompt-lib`, which clones the repo and resolves relative paths against the clone.

**Rationale**:

- Documented to work for git-hosted marketplaces: "Paths resolve relative to the marketplace root."
- Keeps the marketplace + plugin in a single repo with a single git history.
- No need to push the plugin to a second location.

**Alternatives considered**:

- **`source: { source: "github", repo: "owner/prompt-lib" }`**: would clone the whole repo *again* as the plugin source (in addition to the marketplace clone), and would still grab the whole tree (not just `global/`) unless combined with `git-subdir`. More bandwidth, no benefit.
- **`source: { source: "git-subdir", url: "...", path: "global" }`**: works but adds verbosity. Relative path achieves the same outcome with one field.

---

## R4. Versioning strategy

**Decision**: Omit the `version` field from both `plugin.json` and the marketplace entry. The plugin's effective version becomes the git commit SHA, so every commit users update to is treated as a new version.

**Rationale**:

- Matches today's "actively-developed personal library" cadence — no release ceremony, no manual version bump.
- The plugin docs explicitly recommend this for "internal or team plugins under active development."
- Avoids the documented footgun: setting `version` in `plugin.json` without bumping it on every release silently masks new commits.

**Alternatives considered**:

- **Semver in `plugin.json`** (e.g. `"version": "1.0.0"`). Rejected for v1: requires discipline to bump on every release; provides no benefit while there is one user. Can be added later (manifest `version` wins over marketplace `version`, and adding it is a non-breaking change).

---

## R5. Hooks — config shape

**Decision**: Translate the inline `hooks` block from `global/settings.json` 1-to-1 into `global/hooks/hooks.json`, replacing every `$USERPROFILE/.claude/hooks/...` / `$HOME/.claude/hooks/...` path with `${CLAUDE_PLUGIN_ROOT}/hooks/...`. Hook scripts themselves stay in `global/hooks/` unchanged.

**Rationale**:

- The hook event names, matchers, and script logic don't change. Only path resolution changes.
- `${CLAUDE_PLUGIN_ROOT}` is the documented variable for referencing bundled plugin files. It resolves to the cache location at runtime and survives plugin updates.
- The apply-path version (`~/.claude/settings.json` with `$USERPROFILE/.claude/hooks/...`) and the plugin-path version (`hooks/hooks.json` with `${CLAUDE_PLUGIN_ROOT}/hooks/...`) coexist cleanly — they reference different copies of the same scripts.

**Alternatives considered**:

- **Inline hooks in `plugin.json`.** Rejected: harder to read than a dedicated file, and the docs show `hooks/hooks.json` as the canonical layout.

### Hook-by-hook mapping

| Event | Matcher | Old command (apply path) | New command (plugin) |
|---|---|---|---|
| `SessionStart` | — | `powershell -ExecutionPolicy Bypass -File $USERPROFILE/.claude/hooks/session-start.ps1` | `powershell -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/hooks/session-start.ps1"` |
| `PreToolUse` | `Bash` | `python "$HOME/.claude/hooks/command_guard.py"` | `python "${CLAUDE_PLUGIN_ROOT}/hooks/command_guard.py"` |
| `PreToolUse` | `PowerShell` | `python "$USERPROFILE/.claude/hooks/command_guard.py"` | `python "${CLAUDE_PLUGIN_ROOT}/hooks/command_guard.py"` |
| `PreToolUse` | `Write` | `python "$USERPROFILE/.claude/hooks/file_write_guard.py"` | `python "${CLAUDE_PLUGIN_ROOT}/hooks/file_write_guard.py"` |
| `PreToolUse` | `Edit` | `python "$USERPROFILE/.claude/hooks/file_write_guard.py"` | `python "${CLAUDE_PLUGIN_ROOT}/hooks/file_write_guard.py"` |
| `PostToolUse` | `Write` | `python "$USERPROFILE/.claude/hooks/write_audit.py"` | `python "${CLAUDE_PLUGIN_ROOT}/hooks/write_audit.py"` |
| `PostToolUse` | `Edit` | `python "$USERPROFILE/.claude/hooks/write_audit.py"` | `python "${CLAUDE_PLUGIN_ROOT}/hooks/write_audit.py"` |
| `Stop` | — | `powershell -ExecutionPolicy Bypass -File $USERPROFILE/.claude/hooks/stop-session.ps1` | `powershell -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/hooks/stop-session.ps1"` |

The `.ps1` interpreter on non-Windows hosts: existing scripts assume `powershell.exe`. Plan task: add a sibling `session-start.sh` / `stop-session.sh` that the README documents users can swap to manually, or accept the same Windows-first constraint as today. Treated as a follow-up, not a v1 blocker — current apply path has the same constraint.

---

## R6. MCP servers — config shape

**Decision**: Extract the `mcpServers` block from `global/settings.json` into a new `global/.mcp.json` file, preserving every server definition verbatim (including `${ENV_VAR}` substitutions, which Claude Code resolves at plugin runtime).

**Rationale**:

- The plugin model's canonical location is `.mcp.json` at plugin root.
- All existing MCP server commands use `pnpm dlx <package>` or `uvx <package>` — no relative paths that need `${CLAUDE_PLUGIN_ROOT}`. So the move is a pure copy.
- Env var references (`${GITHUB_PERSONAL_ACCESS_TOKEN}` etc.) work identically in `.mcp.json` and `settings.json`.

**Alternatives considered**:

- **Inline in `plugin.json` under `mcpServers`.** Rejected: same reason as hooks — separate file is cleaner.
- **Drop the `enabledPlugins` block** (which references `azure@claude-plugins-official` and `microsoft-docs@claude-plugins-official`). Decision: keep it in `settings.json`, not `.mcp.json` — it is a *settings* concern, not an MCP server. Plugin-shipped `settings.json` only supports `agent` and `subagentStatusLine`, so `enabledPlugins` cannot ship via plugin anyway. Stays in the apply path.

---

## R7. Apply-path divergence guard

**Decision**: Add a small "plugin-only files" ignore list to the apply wizard. Files matching any of these patterns under `global/` are NOT copied to `~/.claude/`:

```
.claude-plugin/**
.mcp.json
hooks/hooks.json
```

**Rationale**:

- `~/.claude/.claude-plugin/plugin.json` would be harmless but confusing.
- `~/.claude/.mcp.json` would be ignored by Claude Code (only project-scope `.mcp.json` is loaded), so harmless but pointless.
- `~/.claude/hooks/hooks.json` is the dangerous one: it would *not* be loaded by Claude Code at the user scope (hooks are inline in `settings.json` for the user scope), so harmless. But omitting it keeps `~/.claude/hooks/` exclusively script files, which matches the existing layout.

**Why a small ignore list, not a wholesale restructure**: the apply path already handles `global/` → `~/.claude/` with a copy. Adding three pattern exclusions is one minimal commit; restructuring the repo is many.

**Alternatives considered**:

- **Move the plugin manifest outside `global/`.** Rejected: forces the plugin source path in `marketplace.json` to be `./` (the repo root), which drags the whole repo into the plugin cache.
- **Make `global/` the apply source but a non-`global/` directory the plugin source, copying files between them at build time.** Rejected: build step adds drift risk.
- **Detect and warn instead of skipping.** Rejected: too noisy for a wizard that already works silently.

---

## R8. CLAUDE.md, rules, settings, project-templates — scope split

**Decision**: These items are explicitly out of plugin scope and stay on the apply path. Document the split in `global/MCP.md` (or a new `docs/plugin-install.md`).

**Items NOT shipped via plugin:**

| File | Why not shippable | Stays on apply path? |
|---|---|---|
| `global/CLAUDE.md` | Plugin docs: "A `CLAUDE.md` file at the plugin root is not loaded as project context." | Yes |
| `global/rules/*.md` | No plugin component type for conditional path-pattern rules. They are project-local in Claude Code's model. | Yes |
| `global/project-templates/*.md` | Used by `@init-project` agent as scaffolding source. Agent reads them at runtime; plugin model has no equivalent. | Yes |
| `global/keybindings.json` | No plugin manifest field for keybindings. | Yes |
| `global/statusline.py` | Set via `settings.json.statusLine`, which plugin `settings.json` doesn't support. | Yes |
| `global/settings.json` (permissions, model, theme, defaultMode, statusLine, enabledPlugins) | Plugin `settings.json` only supports `agent` and `subagentStatusLine`. | Yes |
| `global/DESIGN.md`, `architect.md`, `README.md`, `MCP.md` | Documentation, not loadable Claude Code components. | Yes (as documentation) |
| `global/git/hooks/*` | Git hooks (pre-commit etc.), not Claude Code hooks. Separate mechanism. | Yes |

**Rationale**: the plugin model deliberately doesn't allow plugins to override global behavior, permissions, or instructions — that's a security boundary. Trying to work around it would be both fragile and wrong.

**Items shipped via plugin:**

| File / dir | Plugin location |
|---|---|
| `global/skills/*` | `skills/` (auto-discovered) |
| `global/agents/*.md` | `agents/` (auto-discovered) |
| `global/output-styles/*.md` | `output-styles/` (default) — but `outputStyles` field in `plugin.json` can pin if needed |
| `global/hooks/*.py`, `global/hooks/*.ps1` | `hooks/` (referenced from `hooks/hooks.json`) |
| MCP servers from `global/settings.json` | `global/.mcp.json` (new file) |

---

## R9. Local testing workflow

**Decision**: Contributors use `claude --plugin-dir ./global` from the repo root to test plugin changes without publishing. Add a one-liner to `README.md`.

**Rationale**:

- `--plugin-dir` is the documented dev loop. It loads the plugin directly from disk, no cache copy.
- Path is stable (`./global`) — same as the marketplace `source` value, so what works locally works after publish.
- `/reload-plugins` picks up edits without restart (per plugin docs).

**Alternatives considered**:

- **Push to a personal fork + install from there.** Rejected: too slow for iteration.

---

## R10. Validation strategy

**Decision**: Three layers:

1. **Manifest schema** — `claude plugin validate .` in CI (or pre-commit if available). Validates `marketplace.json`, `plugin.json`, frontmatter, `hooks/hooks.json`.
2. **Smoke test** — a documented manual checklist: install on a clean machine, verify a representative skill, agent, hook, MCP server, and output style all work. Lives at `specs/004-github-plugin/quickstart.md`.
3. **Apply-path regression** — a small script (`setup/tools/diff-apply-vs-pre.ps1`) that diffs `~/.claude/` produced by the wizard before and after the feature. Optional, gated.

**Rationale**: Plugins are mostly declarative — schema validation catches most failure modes. Behavioural failures (a hook script crash, a missing env var) surface immediately to the user with a clear error message.

**Alternatives considered**:

- **Full pytest integration test** spawning Claude Code in `-p` mode. Deferred: scope creep for v1. The quickstart checklist + `claude plugin validate` cover the failure modes that matter.

---

## R11. Constitution alignment

Mapped at this point so the plan's Constitution Check can cite this section.

| Constitution principle | Touched? | How this design honors it |
|---|---|---|
| I. Spec-First Conformance | Yes | This feature implements the Claude Code plugin contract (manifest + marketplace schemas). Both schemas are pinned via the contracts in `./contracts/`. |
| II. Subagent Delegation | Yes | Plan delegates manifest authoring and script edits to `main` (cross-cutting JSON config and no specialist matches); script verification to `@code-plan-verifier`. |
| III. Contract Tests Before Implementation | Yes | The two contract docs in `./contracts/` define the schema surface. The validation script (`claude plugin validate`) is the contract test. It MUST exist before the manifest files are considered complete. |
| IV. Reversible Config Changes | Yes | Every file added under `global/` (plugin.json, .mcp.json, hooks/hooks.json) is just additional declarative config; reverting = delete the files + revert the apply-wizard ignore-list patch. |
| V. Minimal Skill & Agent Surface | Yes | Zero new skills, zero new agents added. The plugin merely re-packages what already ships. |
| VI. Parallel Isolation | N/A | No parallel writing subagents in any phase. |

No gate violations. No complexity-tracking entries needed.
