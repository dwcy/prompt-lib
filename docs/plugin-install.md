# Install prompt-lib as a Claude Code plugin

This page is the user-facing install guide for the GitHub plugin path. The full design, alternatives considered, and constitution-gate justification live in [`specs/004-github-plugin/`](../specs/004-github-plugin/). To verify the install works locally before publishing, run `python setup/tools/validate-plugin.py` from the repo root — it runs `claude plugin validate`, the MCP parity check, and the hooks parity check.

---

## Three install paths

| Path | For who | What it ships |
|---|---|---|
| **Plugin (this page)** | Anyone who just wants the slash commands, agents, hooks, MCP servers — no clone, no Python script, namespaced as `/prompt-lib:*`. Best for teammates, second machines, evaluators. | Skills, agents, output-styles, hooks, MCP servers. |
| **`cabal` from PyPI** ([setup/README](../setup/README.md)) | Anyone who wants the full setup including global behaviour rules, permissions, theme, statusline, file-pattern rules, project templates — without cloning the repo. | All of the above **plus** `global/CLAUDE.md`, `global/rules/`, `global/project-templates/`, `global/keybindings.json`, `global/statusline.py`, and the `settings.json`-level fields. Run via `uv tool install cabal` then `cabal`. |
| **Apply script** (git checkout + [setup/](../setup/README.md)) | Power users who already have a clone of prompt-lib and want to run the wizard or apply script directly from source. | Same surface as `cabal`, just driven from `python setup/settings-configurator-ui.py` against the local working tree. |

The three paths are complementary, not exclusive. The plugin is the lightest channel (slash-commands only). The `cabal` package is the full wizard without needing a clone. The apply script is for contributors.

---

## Install (plugin path)

Inside any Claude Code session:

```text
/plugin marketplace add <github-owner>/prompt-lib
/plugin install prompt-lib@prompt-lib
```

Replace `<github-owner>` with the actual GitHub owner of the repo. Default install scope is `user` (available in every project on the machine). To scope to one project, append `--scope project`.

That's it. No clone, no Python install, no script run.

### Verify

```text
/plugin list             # → prompt-lib@prompt-lib   enabled
/help                    # → /prompt-lib:git, /prompt-lib:commit, /prompt-lib:review, …
/agents                  # → prompt-lib:python-architect, prompt-lib:react-architect, …
```

### Update

```text
/plugin update prompt-lib@prompt-lib
```

The plugin omits an explicit `version`, so every new commit on the default branch counts as a new version — running `/plugin update` always pulls the latest. (See spec research R4 for the reasoning.)

### Disable / re-enable (without uninstall)

```text
/plugin disable prompt-lib@prompt-lib
/plugin enable prompt-lib@prompt-lib
```

### Uninstall

```text
/plugin uninstall prompt-lib@prompt-lib
```

`~/.claude/` is not touched.

---

## Prerequisites

Same prerequisites as the apply path. The plugin doesn't ship interpreters or runtimes.

| For | Need |
|---|---|
| Python hooks (`command_guard.py`, `file_write_guard.py`, `write_audit.py`) | Python 3 on PATH |
| PowerShell hooks (`session-start.ps1`, `stop-session.ps1`) | `powershell` (Windows) or `pwsh` (Linux/macOS) |
| MCP servers | `pnpm dlx` (Node.js packages) and `uvx` (uv) |
| Private-repo install | `gh auth login` (or `GITHUB_TOKEN` env for background auto-updates) |
| MCP server env vars | See the table below |

### MCP server env vars

Each server with secrets requires the env var(s) below to be set in your shell. Missing vars cause only the affected server to fail at startup; the plugin install and other servers keep working.

| Server | Env var(s) |
|---|---|
| `figma` | `FIGMA_ACCESS_TOKEN` |
| `azure-devops` | `AZURE_DEVOPS_ORG_URL`, `AZURE_DEVOPS_TOKEN` |
| `supabase` | `SUPABASE_ACCESS_TOKEN` |
| `obsidian` | `OBSIDIAN_API_KEY`, `OBSIDIAN_HOST`, `OBSIDIAN_PORT` |
| `context7`, `playwright`, `docker` | (no env required) |

For setup help — including the Windows wizard mode that initialises these vars for you — see [`setup/env/README.md`](../setup/env/README.md).

---

## What the plugin ships vs what stays on the apply path

| Item | Plugin | Apply |
|---|:-:|:-:|
| Skills (`global/skills/`) | ✅ as `/prompt-lib:<name>` | ✅ as `/<name>` |
| Agents (`global/agents/`) | ✅ as `prompt-lib:<name>` | ✅ as `<name>` |
| Output styles (`global/output-styles/`) | ✅ | ✅ |
| Hooks (Python + PowerShell scripts in `global/hooks/`) | ✅ via plugin `hooks/hooks.json` | ✅ via `~/.claude/settings.json` |
| MCP servers (8 servers) | ✅ via plugin `.mcp.json` | ✅ via `~/.claude/settings.json` |
| Global `CLAUDE.md` (behavioural rules: commits, code style, env files, etc.) | ❌ — plugin model doesn't auto-load `CLAUDE.md` | ✅ |
| `global/rules/*.md` (file-pattern conditional rules: `csharp.md`, `react.md`, `tests.md`, `typescript.md`) | ❌ — no plugin component type for these | ✅ |
| `global/project-templates/*.md` (used by `@init-project`) | ❌ | ✅ |
| Global `settings.json` permissions / model / theme / statusLine / defaultMode | ❌ — plugin `settings.json` only supports `agent` + `subagentStatusLine` | ✅ |
| `global/keybindings.json` | ❌ | ✅ |

If you want **everything**, run the apply script too. The two paths coexist; plugin skills get the namespace prefix and apply skills stay flat, so invocation is unambiguous. Hooks may double-fire if both are active — pick one path or remove the duplicate.

---

## Local development (for contributors)

From a clone of the repo:

```bash
claude --plugin-dir ./global
```

This loads the plugin directly from disk — no cache copy, no marketplace round-trip. Iterate on a skill or agent, then run `/reload-plugins` to pick up the changes without restarting Claude Code.

This is the same path `claude plugin validate .` uses for schema checks.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/plugin marketplace add` says "marketplace not found" | Repo is private and you're not authenticated | Run `gh auth login`. For background updates, set `GITHUB_TOKEN`. |
| Plugin installs but skills don't appear | New install needs a reload | Run `/reload-plugins`, or restart Claude Code. |
| One MCP server fails, the rest work | The failed server needs an env var you haven't set | Set the env var from the table above, then `/reload-plugins`. |
| Hook script doesn't fire | `python` or `powershell` not on PATH | Install the prerequisite. |
| Both plugin and apply installed; hooks fire twice | Both copies are active | Uninstall one: `/plugin uninstall prompt-lib@prompt-lib`, or remove `hooks` from `~/.claude/settings.json`. |

For deeper diagnostics, run `claude --debug` and check the plugin-load section.

---

## Design references

- [`specs/004-github-plugin/spec.md`](../specs/004-github-plugin/spec.md) — user stories, FRs, success criteria.
- [`specs/004-github-plugin/plan.md`](../specs/004-github-plugin/plan.md) — technical context, constitution-gate analysis, delegation map.
- [`specs/004-github-plugin/research.md`](../specs/004-github-plugin/research.md) — 11 decision records (R1–R11): plugin root location, marketplace topology, source type, versioning, hook/MCP shape, apply-path divergence guard.
- [`specs/004-github-plugin/contracts/`](../specs/004-github-plugin/contracts/) — wire-format contracts for `marketplace.json`, `plugin.json`, `hooks/hooks.json`, `.mcp.json` plus the MCP-sync and hooks-sync parity invariants.
- [`specs/004-github-plugin/quickstart.md`](../specs/004-github-plugin/quickstart.md) — install + smoke-test checklist (overlap with this page; this page is the user-facing trimmed version).
- Upstream docs: <https://code.claude.com/docs/en/plugins>, <https://code.claude.com/docs/en/plugins-reference>, <https://code.claude.com/docs/en/plugin-marketplaces>.
