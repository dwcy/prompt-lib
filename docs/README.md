# Docs — prompt-lib

Deeper documentation on what every piece of this repo does, why it exists, and how to compose it into a real multi-agent workflow.

> **One-page visual tour:** [`infographic.html`](infographic.html) — single A4 landscape sheet, no scrolling, 16-cell grid of every feature. Scrollable long-form variant: [`infographic-v1.html`](infographic-v1.html).

## Reading order

1. **Read this first** — [`master-flowchart.md`](master-flowchart.md) — the end-to-end chain of rules in one diagram: session start → branch guard → delegate-or-not → worktree isolation → merge-back → test → verify → audit → commit → PR → cleanup, with every enforcing hook annotated at the point it fires. Editable source: [`master-flowchart.drawio`](master-flowchart.drawio) (open in [diagrams.net](https://app.diagrams.net) or the drawio VS Code extension).
2. [`architecture.md`](architecture.md) — how Claude Code loads context at session start; how agents, skills, MCP tools, hooks, and rules fit together.
3. [`settings.md`](settings.md) — every field in `global/settings.json` explained (model, default mode, statusline, permission allow/deny, MCP servers, hook bindings, enabled plugins).
4. [`agents.md`](agents.md) — what every subagent is for, what tools it has, when Claude picks it autonomously vs. when you `@`-invoke it.
5. [`skills.md`](skills.md) — every slash command: trigger, behaviour, side effects.
6. [`hooks.md`](hooks.md) — `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, `SessionEnd` — when each of the 14 hook scripts fires, what it protects, what it logs.
7. [`rules-output-styles.md`](rules-output-styles.md) — file-pattern conditional rules, response output styles, project-init templates.
8. [`workflows.md`](workflows.md) — multi-agent recipes: spec-kit → worktree → plan → implement → verify → review → finish branch → PR.
9. [`parallel-isolation.md`](parallel-isolation.md) — when concurrent subagents must run in isolated git worktrees, why, and how (`isolation: "worktree"` + `/using-git-worktrees`). Canonical source of the rule.
10. [`speckit.md`](speckit.md) — how spec-kit is configured in this repo: constitution, gates, slash commands, templates, delegation roster, phase-status convention, git-extension override.
11. [`services.md`](services.md) — the `a2a-bridge` and `orchestrator` daemons: where they live, what they do, how they extend Claude Code.
12. [`plugin-install.md`](plugin-install.md) — install prompt-lib as a Claude Code plugin without cloning (no Python script). Covers install commands, the scope split vs. the apply path, prerequisites, local-dev workflow, and troubleshooting. Design lives in [`specs/004-github-plugin/`](../specs/004-github-plugin/).
13. [`release-readiness.md`](release-readiness.md) — what must be true before tagging a package release; includes the package-name decision, PyPI setup, and root test orchestration.
14. [`learning.md`](learning.md) — how to grow muscle memory with this stack: what to learn first, what to skip, how to debug surprises.

## Conventions used in these docs

- **`@agent-name`** — a subagent invocation (Claude either picks it autonomously based on the description match, or you ping it explicitly).
- **`/skill-name`** — a slash-command skill that injects instructions into the current conversation.
- **`hook → event`** — a script bound to a Claude Code lifecycle event in `settings.json`.
- **Read this first** — files marked with this banner are load-bearing; skip them and the rest will feel arbitrary.
