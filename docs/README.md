# Docs — prompt-lib

Deeper documentation on what every piece of this repo does, why it exists, and how to compose it into a real multi-agent workflow.

> **One-page visual tour:** [`infographic.html`](infographic.html) — single A4 landscape sheet, no scrolling, 16-cell grid of every feature. Scrollable long-form variant: [`infographic-v1.html`](infographic-v1.html).

## Reading order

1. [`architecture.md`](architecture.md) — how Claude Code loads context at session start; how agents, skills, MCP tools, hooks, and rules fit together.
2. [`settings.md`](settings.md) — every field in `global/settings.json` explained (model, default mode, statusline, permission allow/deny, MCP servers, hook bindings, enabled plugins).
3. [`agents.md`](agents.md) — what every subagent is for, what tools it has, when Claude picks it autonomously vs. when you `@`-invoke it.
4. [`skills.md`](skills.md) — every slash command: trigger, behaviour, side effects.
5. [`hooks.md`](hooks.md) — `SessionStart`, `PreToolUse`, `PostToolUse`, `Stop` — when they fire, what they protect, what they log.
6. [`rules-output-styles.md`](rules-output-styles.md) — file-pattern conditional rules, response output styles, project-init templates.
7. [`workflows.md`](workflows.md) — multi-agent recipes: spec-kit → worktree → plan → implement → verify → review → finish branch → PR.
8. [`parallel-isolation.md`](parallel-isolation.md) — when concurrent subagents must run in isolated git worktrees, why, and how (`isolation: "worktree"` + `/using-git-worktrees`). Canonical source of the rule.
9. [`speckit.md`](speckit.md) — how spec-kit is configured in this repo: constitution, gates, slash commands, templates, delegation roster, phase-status convention, git-extension override.
10. [`services.md`](services.md) — the `a2a-bridge` and `orchestrator` daemons: where they live, what they do, how they extend Claude Code.
11. [`plugin-install.md`](plugin-install.md) — install prompt-lib as a Claude Code plugin without cloning (no Python script). Covers install commands, the scope split vs. the apply path, prerequisites, local-dev workflow, and troubleshooting. Design lives in [`specs/004-github-plugin/`](../specs/004-github-plugin/).
12. [`release-readiness.md`](release-readiness.md) — what must be true before tagging a package release; includes the package-name decision, PyPI setup, and root test orchestration.
13. [`learning.md`](learning.md) — how to grow muscle memory with this stack: what to learn first, what to skip, how to debug surprises.

## Conventions used in these docs

- **`@agent-name`** — a subagent invocation (Claude either picks it autonomously based on the description match, or you ping it explicitly).
- **`/skill-name`** — a slash-command skill that injects instructions into the current conversation.
- **`hook → event`** — a script bound to a Claude Code lifecycle event in `settings.json`.
- **Read this first** — files marked with this banner are load-bearing; skip them and the rest will feel arbitrary.
