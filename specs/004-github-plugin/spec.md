# Feature Specification: Package prompt-lib as an Installable Claude Code Plugin (v1)

**Feature Branch**: `004-github-plugin`
**Created**: 2026-05-16
**Status**: Draft
**Input**: Package the existing prompt-lib (skills, agents, hooks, MCP servers, output-styles) as an installable Claude Code plugin distributed from GitHub. A second machine — or any other user — should be able to install it with a single `/plugin marketplace add` + `/plugin install` pair, without cloning the repo. The existing apply-script deployment path (`setup/settings-configurator-ui.py` / `setup/tools/apply-global-claude-settings.sh`) MUST continue to work unchanged for users who prefer it; the plugin is an *additional* distribution channel, not a replacement.

## Context

Today, prompt-lib is the source of truth for `~/.claude/` and is deployed via an apply script that copies `global/` into the user's home directory. This works well for the single-machine power-user case but has friction for sharing:

- A teammate has to clone the repo, install Python, run the wizard, and trust the script.
- There is no per-user enable/disable, no version pinning, no marketplace discoverability.
- Updating means `git pull` + re-running the wizard.

Claude Code's plugin system (`/plugin marketplace add` + `/plugin install`) solves exactly these problems: GitHub-hosted marketplaces, namespaced skills (`/prompt-lib:<name>`), version cache, `/plugin update`, scoped install (`user` / `project` / `local`), and zero-touch enable/disable.

This feature adds the plugin distribution channel **without removing the apply path**. The apply path retains items the plugin model cannot ship: the always-loaded global `CLAUDE.md`, the global `settings.json` (permissions, model, theme, statusLine), `rules/` files, and `project-templates/`.

**Explicitly out of scope for v1**: shipping global `CLAUDE.md` as a plugin (the plugin model does not auto-load `CLAUDE.md`); shipping global `settings.json` permissions/model/theme/statusLine (plugin settings only support `agent` and `subagentStatusLine`); a private marketplace; multiple plugins per marketplace; publishing to the official Anthropic marketplace; Node package distribution.

---

## User Scenarios & Testing

### User Story 1 — One-Command Install From GitHub (Priority: P1) 🎯 MVP

A new user (a teammate, a second machine, or a stranger who finds the repo) wants the prompt-lib skills, agents, hooks, and MCP servers available in their Claude Code session. They run two commands inside Claude Code and the plugin is installed, namespaced, and immediately usable — without cloning the repo, installing Python, or running any script.

**Why this priority**: This is the entire point of the feature. Without P1, the feature has no value.

**Independent Test**: On a clean machine with Claude Code installed and no prior knowledge of prompt-lib, run `/plugin marketplace add <github-owner>/prompt-lib` followed by `/plugin install prompt-lib@prompt-lib`. Open `/help` — every prompt-lib skill appears under the `prompt-lib:` namespace, every agent appears in `/agents`, and the prompt-lib MCP servers appear in the MCP tools list.

**Acceptance Scenarios**:

1. **Given** a fresh Claude Code install, **When** the user runs `/plugin marketplace add <owner>/prompt-lib`, **Then** the marketplace appears in `/plugin marketplace list` and reports the catalog name `prompt-lib` with one plugin available.
2. **Given** the marketplace is added, **When** the user runs `/plugin install prompt-lib@prompt-lib`, **Then** the plugin is fetched from GitHub, installed into the user scope by default, and `/plugin list` shows it as enabled.
3. **Given** the plugin is installed, **When** the user opens `/help`, **Then** every shipped skill appears as `/prompt-lib:<skill-name>` (namespaced), and invoking one runs the same logic as the apply-script-installed copy.
4. **Given** the plugin is installed, **When** the user opens `/agents`, **Then** every shipped subagent (`@python-architect`, `@react-architect`, etc.) appears under the `prompt-lib` namespace.
5. **Given** the plugin is installed, **When** Claude Code starts, **Then** the prompt-lib MCP servers (context7, github, figma, playwright, etc.) initialize without error provided the user has set the required env vars.

---

### User Story 2 — Apply-Script Path Keeps Working Unchanged (Priority: P1) 🎯 MVP

An existing prompt-lib user who has been deploying via `python setup/settings-configurator-ui.py` continues to do exactly that after this feature ships. Their workflow, the contents of `~/.claude/`, and the behaviour of every skill, agent, hook, and MCP server they were using stay identical. No file they care about moves; no setting they rely on disappears.

**Why this priority**: The constitution's Reversible Config Changes principle and the user's explicit instruction ("make sure everything still works") make this a non-negotiable invariant. A plugin packaging that breaks the apply path is unacceptable.

**Independent Test**: With the feature merged but no plugin installed, run `python setup/settings-configurator-ui.py` against a clean `~/.claude/` and verify: every file present before the feature is present after; every skill, agent, hook, and MCP server invocation works identically; `~/.claude/settings.json` contains the same `mcpServers`, `hooks`, `permissions`, `statusLine`, `model`, and `theme` values as before.

**Acceptance Scenarios**:

1. **Given** a user on the prior commit (003-issue-triage tip), **When** they pull the feature branch and re-run the apply wizard, **Then** their `~/.claude/` ends up with the same set of files as before, plus only additive plugin-related files (the wizard explicitly excludes plugin-only manifest files from being deployed to `~/.claude/`).
2. **Given** the apply wizard ran, **When** the user invokes any prompt-lib skill by its short name (e.g. `/commit`, `/git`, `/review`), **Then** it runs as before — no namespace prefix required.
3. **Given** the apply wizard ran, **When** Claude Code starts, **Then** the session-start, command-guard, file-write-guard, write-audit, and stop-session hooks fire as before.
4. **Given** the apply wizard ran, **When** the user inspects `~/.claude/settings.json`, **Then** `mcpServers`, `hooks`, `permissions`, `statusLine`, `model`, `theme`, and `defaultMode` are identical to what the prior `global/settings.json` produced.
5. **Given** a user has *both* the apply-deployed copy AND the plugin installed, **When** they invoke a skill, **Then** behaviour is well-defined (either path works) and `/doctor` does not flag a structural error.

---

### User Story 3 — Versioned Updates From GitHub (Priority: P2)

After the plugin is installed, the maintainer pushes a new commit to the GitHub repo (e.g. a new skill or a bugfix to an existing one). Installed users get the update by running `/plugin update prompt-lib@prompt-lib`, without re-cloning or re-running any script.

**Why this priority**: The whole point of using a marketplace over a `git clone` is centralised update management. Without P3, users would still have to manually re-sync.

**Independent Test**: Install the plugin from commit A. Push commit B containing a new skill `/hello`. Run `/plugin update prompt-lib@prompt-lib`. Verify `/prompt-lib:hello` is now invokable.

**Acceptance Scenarios**:

1. **Given** the plugin is installed at commit A and the maintainer pushes commit B, **When** the user runs `/plugin update prompt-lib@prompt-lib`, **Then** Claude Code fetches commit B and the new skill appears.
2. **Given** the maintainer pushes a commit that *removes* a skill, **When** the user updates, **Then** the skill disappears from `/help` and is no longer invokable.
3. **Given** the user is on the latest commit, **When** they run `/plugin update`, **Then** Claude Code reports "already at the latest version" and does not re-download.

---

### User Story 4 — Disable Without Uninstall (Priority: P3)

A user wants to temporarily turn off prompt-lib (e.g. to test a conflicting plugin from another marketplace, or to debug whether a prompt-lib hook is interfering with something) without losing the install.

**Acceptance Scenarios**:

1. **Given** the plugin is installed and enabled, **When** the user runs `/plugin disable prompt-lib@prompt-lib`, **Then** all prompt-lib skills, agents, hooks, and MCP servers stop appearing.
2. **Given** the plugin is disabled, **When** the user runs `/plugin enable prompt-lib@prompt-lib`, **Then** everything reappears with no re-download.

---

### Edge Cases

- **User has an env var unset that an MCP server needs** (e.g. `GITHUB_PERSONAL_ACCESS_TOKEN`): the affected MCP server fails to start, but the plugin install succeeds and other servers still work. The README documents required env vars.
- **User on Windows installs the plugin**: Python-based hooks (`command_guard.py`, `file_write_guard.py`, `write_audit.py`) require Python on PATH; PowerShell-based hooks (`session-start.ps1`, `stop-session.ps1`) require pwsh or powershell. Documented in README; same prerequisites as today's apply path.
- **User installs both the plugin and the apply-deployed copy**: skills, agents, and hooks may register twice. Claude Code's namespacing puts plugin skills under `/prompt-lib:<name>` while apply skills stay at `/<name>`, so invocation is unambiguous. Hooks may fire twice — the README warns against running both paths simultaneously.
- **Plugin install on a private fork**: works the same as install from the public repo provided the user is git-authenticated (`gh auth login`, SSH agent, or `GITHUB_TOKEN` env for background updates).
- **Marketplace catalog moves to a different GitHub owner**: users must run `/plugin marketplace remove prompt-lib` then re-add from the new owner. Documented.
- **Plugin cache corruption**: standard `/plugin` recovery applies — Claude Code re-fetches on next session start.

---

## Requirements

### Functional Requirements

- **FR-201**: The repository MUST contain a valid Claude Code marketplace catalog at `.claude-plugin/marketplace.json`, declaring a marketplace named `prompt-lib` with at least one plugin entry.
- **FR-202**: The repository MUST contain a valid Claude Code plugin manifest at a stable relative path inside the repo, declaring a plugin named `prompt-lib`.
- **FR-203**: The plugin MUST be installable from GitHub via the two commands `/plugin marketplace add <owner>/prompt-lib` and `/plugin install prompt-lib@prompt-lib` without any additional setup.
- **FR-204**: The installed plugin MUST expose every skill currently under `global/skills/` as `/prompt-lib:<skill-name>`.
- **FR-205**: The installed plugin MUST expose every subagent currently under `global/agents/` under the `prompt-lib` namespace.
- **FR-206**: The installed plugin MUST register every hook currently configured in `global/settings.json` (`SessionStart`, `PreToolUse(Bash|PowerShell|Write|Edit)`, `PostToolUse(Write|Edit)`, `Stop`) via `hooks/hooks.json`, using `${CLAUDE_PLUGIN_ROOT}` for all script paths.
- **FR-207**: The installed plugin MUST register every MCP server currently configured in `global/settings.json` (`context7`, `github`, `figma`, `playwright`, `azure-devops`, `supabase`, `obsidian`, `docker`) via `.mcp.json` at plugin root.
- **FR-208**: The installed plugin MUST expose every output style currently under `global/output-styles/` via the `outputStyles` manifest field.
- **FR-209**: The plugin MUST work on Windows, Linux, and macOS. Where a hook currently has a `.ps1` variant, the plugin MUST route to the right interpreter for the host OS (or document the prerequisite).
- **FR-210**: The apply-script flow (`python setup/settings-configurator-ui.py` and `setup/tools/apply-global-claude-settings.sh`) MUST continue to deploy `global/` into `~/.claude/` with no behaviour change visible to end users of the apply path.
- **FR-211**: The apply script MUST NOT copy plugin-only files into `~/.claude/` (specifically: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, plugin-only `hooks/hooks.json`, plugin-only `.mcp.json`). It MAY copy them harmlessly, but they must not produce duplicate or conflicting state.
- **FR-212**: The plugin manifest MUST omit the `version` field so every new commit on the default branch counts as a new version (matches the current "actively-developed personal lib" cadence; explicit semver can be added later without breaking change).
- **FR-213**: The plugin's hooks, MCP server commands, and any scripts MUST use `${CLAUDE_PLUGIN_ROOT}` to reference bundled files. No path may assume the plugin is at `~/.claude/`.
- **FR-214**: The plugin MUST NOT attempt to ship the global `CLAUDE.md`, `global/rules/`, `global/project-templates/`, `global/keybindings.json`, `global/statusline.py`, or `global/settings.json`-level fields (`permissions`, `model`, `theme`, `defaultMode`, `statusLine`). These remain managed by the apply path. The README MUST document this scope split.
- **FR-215**: The plugin MUST pass `claude plugin validate` against the manifest and marketplace files.
- **FR-216**: The `global/MCP.md` documentation MUST be updated (or a new `docs/plugin-install.md` added) to document the install commands, scope split with the apply path, and required env vars.
- **FR-217**: Local development of the plugin MUST be supported via `claude --plugin-dir ./global` (or whichever subdir hosts the manifest), so contributors can test changes without publishing.
- **FR-218**: A contract-style validation script MUST exist that exercises both install paths against a clean cache and asserts that the resulting skill/agent/hook/MCP inventory matches expectation. Acceptable forms: a bash + bats script, a Python pytest, or a documented manual checklist with screenshots.

### Key Entities

- **Marketplace catalog** (`.claude-plugin/marketplace.json`): the discovery file. Declares marketplace name, owner, and one plugin entry pointing to the plugin's location inside this repo.
- **Plugin manifest** (`<plugin-root>/.claude-plugin/plugin.json`): the plugin's identity. Declares name, description, author, optional `mcpServers`/`hooks`/`outputStyles` pointers.
- **Plugin root**: the directory inside this repo that holds the plugin manifest and component subdirectories. Whether this is `global/`, the repo root, or a new `plugin/` subdir is a design decision the plan must justify.
- **MCP config** (`<plugin-root>/.mcp.json`): the plugin's MCP server registry.
- **Hooks config** (`<plugin-root>/hooks/hooks.json`): the plugin's hook registry.

---

## Success Criteria

- **SC-201**: From a clean Claude Code install with no prior knowledge of prompt-lib, a user can go from "I heard about prompt-lib" to "every prompt-lib skill works in my session" in under 2 minutes and using exactly 2 commands inside Claude Code. No clone, no Python install, no script.
- **SC-202**: After the feature ships, an existing apply-path user pulls and re-runs the wizard. Zero files in `~/.claude/` differ in a behaviour-affecting way from the pre-feature state. (File timestamps and the wizard's own logs may differ; user-observable behaviour does not.)
- **SC-203**: The full set of skills, agents, hooks, MCP servers, and output styles available to a plugin-installed user is a superset of {skills, agents, hooks, MCP servers, output styles} declared in scope (FR-204 through FR-208). No item from scope is missing.
- **SC-204**: `claude plugin validate` returns success against the marketplace and plugin manifests with zero errors and zero blocking warnings. (Non-blocking warnings about kebab-case or missing description are acceptable only if intentional and documented.)
- **SC-205**: A user who installs the plugin, pushes a new skill on a branch, then runs `/plugin update` against that branch (via a `ref`-pinned marketplace entry or by changing the marketplace catalog) sees the new skill within one `/plugin update` invocation.
- **SC-206**: Disabling the plugin via `/plugin disable` removes all prompt-lib skills, agents, hooks, and MCP servers from the session within one Claude Code restart. Re-enabling restores them without re-download.

## Assumptions

- The repo is (or will be) hosted on GitHub at a stable `owner/repo` slug discoverable by the user; if not currently public, the user installing has `gh auth login` set up.
- Claude Code version is recent enough to support the `/plugin` command set (the `--plugin-dir` flag and `/plugin marketplace add` are present on the user's install).
- Hook script prerequisites (Python 3 on PATH for the Python hooks, PowerShell or pwsh for the `.ps1` hooks) are present on the user's machine — same prerequisite as the apply path today.
- MCP server env vars (`GITHUB_PERSONAL_ACCESS_TOKEN`, `FIGMA_ACCESS_TOKEN`, `AZURE_DEVOPS_ORG_URL`, `AZURE_DEVOPS_TOKEN`, `SUPABASE_ACCESS_TOKEN`, `OBSIDIAN_*`) are set by the user out-of-band — same as today.
- Users on private forks have configured a credential helper or set `GITHUB_TOKEN` for background auto-updates.
- The plugin name `prompt-lib` is acceptable as the public namespace — every shipped skill becomes `/prompt-lib:<name>` and that prefix is fine.
- No other plugin a user has installed will conflict with the `prompt-lib` namespace.
- Reversibility: a user can fully uninstall via `/plugin uninstall prompt-lib@prompt-lib`, leaving `~/.claude/` untouched.
