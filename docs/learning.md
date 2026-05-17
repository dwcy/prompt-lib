# Learning path — getting fluent with this stack

This stack is opinionated and dense. There's a fast way and a slow way to learn it. The fast way:

## Day 1 — get it running

1. Read [`architecture.md`](architecture.md) end-to-end. Skip nothing. The five-step boot is the only model you need.
2. Run `python setup/settings-configurator-ui.py`. Try every mode (Update / Doctor / Restore). The wizard is reversible — explore.
3. Open Claude Code in any project. Watch the `SessionStart` hook fire — it either offers to scaffold `CLAUDE.md` or says "@load-project will brief you."
4. Type `/git`. Observe how the skill body becomes the next instruction. That's the whole skill model.

**By end of day 1**: you understand session boot, deployment, and the skill mechanism.

## Day 2 — understand the routing

1. Read [`agents.md`](agents.md). Note the *description fields* — each one is engineered to win autonomous routing only for its real trigger.
2. Read [`skills.md`](skills.md). Notice the same pattern — descriptions name trigger phrases ("Use when…", "Use after…").
3. Pick three skills you'd realistically use this week (e.g. `/git`, `/pr`, `/review`) and try them on a real branch.
4. Try invoking one agent explicitly: `@code-plan-verifier check this against the plan` — observe how the subagent runs in isolation and returns a single message.

**By end of day 2**: you know which tool fires when, and you can predict routing before you type.

## Day 3 — make changes safely

1. Read [`settings.md`](settings.md). Pay particular attention to `permissions.allow` / `permissions.deny`. These are the difference between a permission-prompt-spam session and a smooth one.
2. Read [`hooks.md`](hooks.md). The two security guards (`command_guard.py`, `file_write_guard.py`) are load-bearing — understand what they protect before you touch them.
3. Customise something small: add a permission to `allow`, deploy, restart, see it work. Then revert via the wizard's Restore mode.

**By end of day 3**: you know how to extend safely and how to roll back.

## Day 4 — compose

1. Read [`workflows.md`](workflows.md). Pick **Workflow 1** (single-session spec-kit feature) and run it against a small real feature.
2. Then try **Workflow 2** (parallel sessions with worktrees). This is where the leverage compounds — implementer in one window, reviewer in another.
3. Read [`services.md`](services.md). You don't need to run the orchestrator to learn from it — the spec tree under `specs/002-agent-orchestrator/` is the best example of how this repo "thinks" about feature design.

**By end of day 4**: you've shipped one feature using the canonical flow.

## Day 5 — author your own

1. Use `/skill-create` to capture a workflow you keep doing manually.
2. Add a new agent for a domain you work in. The roster pattern (description-driven autonomous routing, narrow tool set, focused system prompt) generalises to anything.
3. Read `global/README.md` for the deeper "why" on plugins, MCP scopes, and template authoring.

**By end of day 5**: you're contributing back to the repo, not just consuming it.

## Mental shortcuts that will save you time

- **"Where does this live?"** Source under `global/`, deployed under `~/.claude/`. Edit at the source, never at the deploy target.
- **"Why did Claude pick that tool?"** It read the `description:` and matched. If routing surprises you, the description is the bug.
- **"Why won't Claude pick my tool?"** Same answer. Lead with a verb. Name the trigger phrase.
- **"Why is my skill polluting the conversation?"** It probably should have been an agent (context isolation).
- **"Why is my agent's output too summarised?"** It probably should have been a skill (runs in your conversation; you see everything).
- **"Should this be in CLAUDE.md or a rule?"** If it applies always → CLAUDE.md. If it only applies to specific files → rule with a `paths:` glob.
- **"My MCP server isn't authenticating."** The env var is missing in the shell that launched Claude Code. Restart the shell after running the wizard's "Initialize env vars" mode.
- **"My change didn't take effect."** You forgot to run `setup/settings-configurator-ui.py` or to restart Claude Code. Both are required.

## Debugging surprises

When something behaves unexpectedly:

1. Open `~/.claude/write_audit.jsonl` and grep by timestamp — every Write/Edit is logged.
2. Run the wizard's "Doctor" mode — it diffs `~/.claude/` against the source in `global/` and shows drift.
3. Check `claude mcp list` for MCP server health.
4. Run `/output-style concise` to strip framing during debugging — the model's actual reasoning becomes visible.

## What NOT to do

- Don't paste literal Unicode into `command_guard.py` — the `\u`-escaped table is intentional. See [`hooks.md`](hooks.md#pretooluse-bash--powershell--command_guardpy).
- Don't bypass `permissions.deny`. The four blocked patterns (`rm -rf /`, force-push, hard-reset, `clean -fd`) exist for a reason.
- Don't put domain-specific rules in `~/.claude/CLAUDE.md`. Use a `rules/` file with a `paths:` glob.
- Don't write skills that try to be open-ended. If the work needs exploration, write an agent.
- Don't commit on `main` — every git skill in this repo refuses, and you should refuse manually too.

## Further reading

| Want to understand | Read |
|---|---|
| Session boot | [`architecture.md`](architecture.md) |
| What every config field does | [`settings.md`](settings.md) |
| What every subagent is for | [`agents.md`](agents.md) |
| What every slash command does | [`skills.md`](skills.md) |
| What every hook protects | [`hooks.md`](hooks.md) |
| How rules, styles, templates differ | [`rules-output-styles.md`](rules-output-styles.md) |
| How to compose agents and skills | [`workflows.md`](workflows.md) |
| What the runtime services do | [`services.md`](services.md) |
