# Global Claude Preferences

Personal preferences and conventions that apply to every project and session.

## Communication

- Be concise. Skip preamble and closing pleasantries.
- Lead with code or the direct answer — explain only what is non-obvious.
- When I ask for an opinion, give one. Don't hedge with "it depends" without a recommendation.
- If something I ask is ambiguous, state your assumption and proceed — don't ask for clarification on minor things.
- Bullet points over paragraphs for lists of things.

## Code style (universal)

- No comments that explain WHAT the code does — only WHY if non-obvious.
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

When a planning skill (`/plan`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`) reaches its done state — all tasks completed, verification passed, the slice is shipped — commit immediately without asking. Keep follow-up changes in small per-feature commits rather than batching.

- **Trigger:** all plan tasks done + verified; or I say "considered done"; or a single self-contained slice finishes in conversation.
- **Pre-flight: stage only this session's changes.** Before editing any file as part of a plan, run `git diff HEAD --name-only` to see what already has uncommitted modifications. If a file you plan to edit was already modified before the session, treat it as off-limits for this commit — either skip the edit, or fold it into the unrelated in-flight work later. Never sweep pre-existing in-flight changes into your auto-commit.
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

**Runtime enforcement**: `global/hooks/pretool_task_isolation.py` blocks background `Task` dispatches that lack `isolation: "worktree"` (unless the subagent is on the read-only allowlist), and `global/hooks/session_start.py` auto-creates a sibling worktree when a second Claude session lands on a feature branch already held by another live session.

See [`docs/parallel-isolation.md`](docs/parallel-isolation.md) for the full rule, edge cases, and anti-patterns.

## Subagent routing

When a task clearly belongs to a specialist domain, invoke `/orchestrate` proactively — do not wait to be asked. The user should not need to know which agent exists.

**Invoke `/orchestrate` automatically when:**
- The task involves .NET / C# architecture or testing
- The task involves Python service design or pytest authoring
- The task involves React, Vue, Next.js, TanStack, or CSS architecture
- The task involves Unity3D scene or MonoBehaviour design
- The task involves Raspberry Pi or Arduino hardware
- The task involves GitHub repo settings configuration
- The user says "write tests", "architect this", "design the UX", or "verify the implementation"
- The task is full-stack (two or more domains) — dispatch parallel agents

**Do not invoke `/orchestrate` for:**
- Quick one-line questions or explanations
- File reads, git commands, or simple edits that need no specialist
- Tasks the user has explicitly asked to handle in the main session

When auto-routing, tell the user: "This looks like a [domain] task — routing to `@<agent>`." before dispatching.

See [`docs/orchestration.md`](docs/orchestration.md) for the full routing table and agent registry.

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
