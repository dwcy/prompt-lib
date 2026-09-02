# Global Claude Preferences

Personal preferences and conventions that apply to every project and session.

## Communication

- Be concise. Skip preamble and closing pleasantries.
- Lead with code or the direct answer — explain only what is non-obvious.
- When I ask for an opinion, give one. Don't hedge with "it depends" without a recommendation.
- If something I ask is ambiguous, state your assumption and proceed — don't ask for clarification on minor things.
- Bullet points over paragraphs for lists of things.

### Explain in plain language

When explaining a problem, a blocker, or a decision I have to make, lead with what is concretely true — the file, the line, what breaks — before any label for it. Assume I have not memorised the project's internal shorthand.

- **Don't make identifiers carry the explanation.** Task IDs (`T042`), requirement codes (`FR-010b`, `SC-003`), and internal terms (`disposition`, `anchor_kind`, `relaxation ladder`) are *references*, not descriptions. Say what the thing does, then cite the ID in parentheses if it's useful for lookup.
- **Show the actual thing.** A three-line code snippet or the literal error text beats a paragraph describing it.
- **When I have to choose, give me the real-world trade-off** — what I gain, what I lose, what it costs to change later — not the names of the options.
- If I say something is unclear, that's a signal to re-explain from concrete facts, **not** to add more detail at the same level of abstraction.

This applies to prose aimed at me. Code comments, commit messages, and spec files keep their normal precision and may use the project's terms freely.

## Searching the codebase

- **Use the `Grep` tool for content search and `Glob` for file lookup — never `grep`/`ls`/`find` via Bash.** They're cheaper, permission-integrated, and don't dump noise into context.
- **One search per question.** No `echo`-header + chained-`grep` shell strings — when an early `grep` exits non-zero the `&&` chain silently swallows the rest. Multiple independent questions → parallel `Grep`/`Glob` calls in one message.
- **Fan-out investigations → dispatch the `Explore` agent** (e.g. "how is the app launched + where's signal handling + what binds X"). It reads the files and returns only the conclusion, so file dumps never enter the main context.
- Bash is still correct for *running* things (git, tests, `python -c` smoke checks) — just not for searching source.
- **Never read generated, dependency, or build-output dirs** — `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `node_modules`, `.venv`/`venv`, `dist`/`build`, `.next`/`.nuxt`, `bin`/`obj`, `publish`/`out`, `target`, `.git`, vendored/`packages`, and the like. They're noise — committed source is the source of truth, not the artifact. Scope `Grep`/`Glob` to source paths and let the tools' default ignores do the rest. Reading into one is a **last resort, only when a bug demands inspecting the actual generated output** (e.g. a build emits wrong code) — and say why when you do.

## Stay inside the working directory

The folder the session starts in is the boundary. Other projects on this machine are not material to look at, sample, or measure against unless I ask for that specific thing — "it would be useful here" is not asking. Exempt: `~/.claude/`, this repo's `global/` tree, and the active toolchain. That much should go without saying; the rest is the part that's easy to miss.

- **Reading is the first half of publishing.** Whatever you read, you may summarise into a file later. Assume every repo I work in may become public.
- **Never record another project's identity** — name, path, solution or package names, namespaces, type or table names. Describe it by shape: "a private 25-project .NET solution, ~86k lines, block-scoped namespaces".
- **Screen- and machine-capture tools** (browser page snapshots, container and process listings, screenshots) write absolute paths and unrelated state into the working directory. Keep their output gitignored and check anything they produced before committing.

## Code style (universal)

- No comments that explain WHAT the code does — only WHY if non-obvious. Exception: XML doc `<summary>` on public .NET types/members is an API-doc convention, not a WHAT comment — keep those (see `/dotnet-class`).
- No dead code, commented-out blocks, or TODO placeholders left behind.
- Prefer explicit over clever — code is read more often than it is written.
- Match the style of the surrounding code when editing existing files.
- Do not change formatting or style of lines I haven't asked you to touch.

## When making changes

- **Branch before starting work.** Before the *first* edit of any task, check the branch. If it's `main`/`master` (or any `refuse_on_branches` entry), create a feature branch first — `git -C <repo> checkout -b <type>/<slug>`, named after the task. Branching is a pre-work step, not part of committing; uncommitted changes follow the checkout, so it's safe to branch late, but branch-first is the habit. Enforced at edit time by `global/hooks/pretool_branch_guard.py` (bypass: `PROMPTLIB_DISABLED_HOOKS=pretool_branch_guard`).
- Only change what is needed to satisfy the request — no refactoring adjacent code.
- If you spot a bug nearby, mention it but don't fix it unless I ask.
- Always read a file before editing it.
- Run the relevant tests after making changes if a test command is known.

## Implementation completeness

- **Full implementation is the default.** Never deliver a half-done "MVP-style" slice unless I explicitly ask for an MVP, prototype, spike, or quick-and-dirty version. Absent those words, the request means the complete, working feature.
- **No silent stubs.** No `NotImplementedError`, placeholder bodies, hardcoded happy-path returns, skipped error handling, or "wire this up later" gaps inside the agreed scope. If something genuinely must be deferred, name it explicitly and get my OK — never let it ride silently.
- **Underspecified → analyse first, then ask.** When the request leaves real decisions open, do the analysis and ask targeted questions until the scope is clear enough to implement fully — don't guess your way into a partial build.
- **Large scope → steer to Spec Kit.** If the work spans multiple features or subsystems, or can't be finished properly in one pass, recommend the Spec Kit flow (`/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks`) instead of starting an ad-hoc partial implementation.
- **"Done" check before stopping.** Before declaring a task complete, re-scan the agreed scope for anything not yet implemented. If in-scope work remains, keep going — done means implemented and verified, not "mostly there".
- **Evidence before claims.** A completion or fix claim needs a freshly run command and its actual output in the report — the tests, the build, the reproduction step. "Should work", "probably fixed", and "seems fine" are not reports; if you have not run it, say it is unverified.
- **Applies to subagents.** Put these expectations in every dispatch brief; when a subagent returns half-done work, send it back rather than accepting it.

## Receiving review feedback

Review comments — from me, a reviewer subagent, or a PR — are claims to verify, not instructions to execute.

- Check each finding against the code before acting on it. Where the reviewer is wrong, say so with the file and line that shows it; where they are right, fix it without ceremony.
- No performative agreement. "You're absolutely right" and "great catch" add nothing; state what you verified and what you changed.
- Before removing or adding something because a review says it is unused or missing, grep for actual usage. Act on what the codebase shows, not on what the comment asserts.
- A review that asks for scope beyond the task is a new request — surface it, don't silently absorb it.

## Versions

- Always prefer the latest stable version of any language, framework, library, or API.
- When suggesting packages, patterns, or syntax — use what is current, not what is familiar from older docs.
- Never suggest deprecated APIs, legacy syntax, or patterns superseded by the framework's current idioms.

## Environment files

- Never generate, write, or edit `.env`, `.env.develop`, `.env.local`, or any env file.
- When env file content is needed, provide exact copy-paste instructions and the content as a code block — do not write the file.
- Env files must be UTF-8 encoded (not UTF-16 / Unicode BOM). State this explicitly in instructions.
- Only `.env.example` is ever committed. All others are gitignored.

## Git commits

When committing — whether I asked via `/git` or just "commit this" — use the `git-identity` wrapper script. All commit-policy values (agent name, agent email, allowed types, branch-refusal list, tag rules) live in **`~/.claude/git-policy.json`** — edit that file to change any of them.

- **Use the wrapper, not raw `git commit`.** The wrapper snapshots your real `--global` identity to `~/.claude/identity/git-original.json` (idempotent, one-time), sets the agent identity in `--local` scope, runs the commit, and restores `--local` after — so your real identity is never overwritten in `--global`.
  ```bash
  python ~/.claude/scripts/git-identity.py commit -m "<type>: <subject>"
  ```
- **Subject line format:** `<type>: <subject>`. The wrapper enforces `<type>` against `policy.allowed_types`. Defaults: `feat | task | fix | refactor | test | docs`. Imperative mood, ≤72 chars, no trailing period.
- **Branch refusal:** the wrapper refuses to commit on any branch listed in `policy.refuse_on_branches` (default `["main", "master"]`). Create a feature branch first (`/git branch <name>`).
- **Multi-paragraph messages:** repeat `-m` per paragraph — `... commit -m "feat: X" -m "Body line 1" -m "Body line 2"`.
- Do **not** add `Co-Authored-By: Claude` trailers — the wrapper's `--local` identity override replaces that convention.
- Show the proposed message and wait for confirmation before committing — **except** at plan-completion checkpoints (see *Auto-commit at plan completion* below).
- Never push unless I explicitly ask.

### Tags, policy editing & recovery

Tags are gated (off by default), the policy file has CLI editors, and a crashed commit can be repaired with `/git-restore-identity` (or `python ~/.claude/scripts/git-identity.py restore`). Full mechanics: [`docs/git-policy.md`](docs/git-policy.md). Don't fall back to raw `git tag` — ask first.

### Auto-commit at plan completion

When a planning skill (`/plan`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`) reaches its done state — all tasks completed, verification passed, the slice is shipped — commit immediately without asking. (For `/plan` that means the plan's tasks have been *executed*, not merely approved — plan approval itself produces nothing to commit.) Keep follow-up changes in small per-feature commits rather than batching.

- **Trigger:** all plan tasks done + verified; or I say "considered done"; or a single self-contained slice finishes in conversation.
- **Pre-flight: stage only this session's changes.** Before editing any file as part of a plan, run `git diff HEAD --name-only` to see what already has uncommitted modifications. If a file you plan to edit was already modified before the session, treat it as off-limits for this commit — either skip the edit, or fold it into the unrelated in-flight work later. Never sweep pre-existing in-flight changes into your auto-commit. Enforced at edit time by `global/hooks/pretool_inflight_guard.py`, which blocks the first edit of any such file once (bypass: `PROMPTLIB_DISABLED_HOOKS=pretool_inflight_guard`).
- **Separate commits per distinct feature**, BUT do not split a single file across two commits via an intermediate file-state dance. If two features both touch `settings.json` (or any shared file), prefer one combined commit ("feat: add X + Y") over rewriting → committing → restoring.
- **Use `git -C <repo>` for every git command.** Never prepend `cd <repo> && git ...` — the harness's safety guardrail treats compound commands as suspicious and denies them, even on a safe branch.
- **Branch-safety check pattern:** the `git-identity` wrapper already enforces `policy.refuse_on_branches`, so a simple one-liner suffices at plan completion:
  ```bash
  python ~/.claude/scripts/git-identity.py commit --repo <repo> -m "<type>: <subject>"
  ```
  If you need to chain a staged-file check first, do it in the same bash invocation:
  ```bash
  git -C <repo> diff --cached --quiet || python ~/.claude/scripts/git-identity.py commit --repo <repo> -m "..."
  ```
- **On a guardrail denial after a verified-safe branch, retry the exact same command once before escalating.** The branch-safety check is occasionally flaky on back-to-back commits and usually clears on retry. Only escalate to me if it denies twice in a row.

## Parallel subagent isolation

When two or more subagents are dispatched to operate concurrently on the same repository, every writing agent MUST run in an isolated git worktree. Concurrent writers on a shared working tree silently overwrite each other.

- **Preferred**: pass `isolation: "worktree"` on the Agent tool call. The harness auto-cleans the worktree if the agent makes no changes; on changes, the path + branch are returned and must be merged.
- **Alternative**: pre-create a worktree via `/using-git-worktrees create <branch>` and brief the subagent with its path as its working directory.
- **Exempt**: read-only agents (no Write/Edit in `tools:`) and sequential single-agent dispatch.

**Runtime enforcement**: `global/hooks/pretool_task_isolation.py` blocks background `Agent` (formerly `Task`) dispatches that lack `isolation: "worktree"` (unless the subagent is on the read-only allowlist), and `global/hooks/session_start.py` auto-creates a sibling worktree when a second Claude session lands on a feature branch already held by another live session.

Both of those need a *live* competing session. For work left behind by a session that already exited — no lock holder, file looks ordinary — `global/hooks/pretool_inflight_guard.py` snapshots the repo's dirty set on this session's first write and blocks the first edit of any file that was already dirty, once.

See [`docs/parallel-isolation.md`](docs/parallel-isolation.md) for the full rule, edge cases, and anti-patterns.

## Subagent routing

**Default: handle the task in the main session.** A subagent dispatch costs a full fresh context (system prompt + CLAUDE.md + re-reading files the main session already has), a round-trip, and — for writing agents — worktree setup and a merge. Delegate only when it buys something the main session can't provide:

- **Scale** — the task is big enough that a fresh context pays for itself: roughly >5 files to change, or work that would dominate this session's context. Single features, bugfixes, and small refactors stay in the main session regardless of domain.
- **Independence** — reviews and audits where fresh unbiased eyes are the value: `@owasp-security-reviewer`, `@code-plan-verifier`, `@secret-auditor`, `@gitignore-auditor`.
- **Parallelism** — two or more genuinely independent workstreams; every writer isolated in a worktree (see *Parallel subagent isolation*). **Hard cap: at most 4 subagents running concurrently** — machine resources, not just tokens. If more are selected, dispatch in waves of ≤4 and start the next wave only as agents finish; never launch a fifth while four are live.
- **Fan-out search** — dispatch the `Explore` agent directly, not `/orchestrate`.

Rules of thumb:

- **Domain match alone is never a reason to delegate.** "It's .NET / React / pytest" doesn't need a specialist; a genuinely hard *design decision* in that domain might. When in doubt, do it in the main session.
- **Vague requests get clarified or analysed in the main session first** — never dispatched vague.
- **Multi-agent pipelines** (requirements → architect → tester → verifier; the designer/UX/CSS trio) run only when I explicitly invoke `/orchestrate` or a Spec Kit flow — never automatically.
- When you do delegate, say what the dispatch buys ("parallel + isolated", "fresh-eyes review", "keeps this context clean") — not just the domain.
- `/orchestrate` stays available on demand: when I type it, run its routing table as written.

See [`docs/orchestration.md`](docs/orchestration.md) for the full routing table and agent registry.

## Recurring & scheduled tasks

`/loop` and `/schedule` are built-in Claude Code skills — available in every session, nothing to install.

- **Suggest `/loop` proactively** when I phrase a task as recurring in *this* session: "keep checking X", "every N minutes", "until it's green/done/merged" — watching CI, babysitting a PR, polling a deploy, draining a work queue, re-running a flaky test until stable.
- **Interval:** pass it explicitly when the cadence is known (`/loop 5m /foo`); omit it to self-pace. Self-pacing: stay under ~4.5 min to keep the prompt cache warm, otherwise commit to 20–30 min idle ticks — never ~5 min (worst of both).
- **`/loop` vs `/schedule`:** `/loop` dies with the session; `/schedule` creates cloud routines that run without a live session. Recurring work that must survive the laptop closing → `/schedule`.
- **House rules apply per iteration:** branch guard, git-identity wrapper, no pushes. A loop never auto-pushes or auto-merges — it reports and waits.
- **Not for:** one-off tasks; polling harness-tracked background work (agents/tasks — completion notifications already fire); anything a hook can do deterministically ("every time X happens" → `/update-config` hooks).

## Package managers

- For frontend and Node.js work, use only `pnpm` or `bun`.
- Never run or suggest `npm`, `npx`, or `yarn` for frontend work. Use `pnpm install`, `pnpm add`, `pnpm run`, `pnpm dlx`, or the matching `bun` / `bunx` command.
- When initializing a new frontend project, always ask which package manager to use: `pnpm` or `bun`.
- If an existing frontend project has only `package-lock.json` or `yarn.lock`, stop and ask whether to migrate to `pnpm` or `bun` instead of using npm/yarn.

## Things to never do

- Never add features I didn't ask for.
- Never rename variables or methods just to satisfy your preference.
- Never commit without being asked explicitly — **except** at plan-completion checkpoints (see *Auto-commit at plan completion*).
- Never push to remote without being asked explicitly.
- Never delete files without confirmation.
- **Never `git checkout --` / `git restore` / `git stash` a file carrying changes you did not make.** Unstaged work exists nowhere but the working tree — no blob in the object store, no reflog entry, nothing to recover. Reverting it is permanent data loss, not an undo. To drop only your own edit to a shared file, re-apply the intended content instead.
- Never read, sample, or measure against code outside the working directory unless I asked for that specific thing (see *Stay inside the working directory*), and never write another project's names or paths into this one.
