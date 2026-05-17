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

When committing — whether I asked via `/git` or just "commit this" — follow the `/git` skill rules:

- Refuse to commit on `main` / `master`. Ask me to create a feature branch first (`/git branch <name>`).
- Subject line: `<type>: <subject>` where type ∈ `feat | task | fix | refactor | test | docs`. Imperative mood, ≤72 chars, no trailing period.
- Always use agent authorship via `-c` flags (do not modify global git config):
  ```
  git commit -c user.email="my@agent.commit" -c user.name="Claude Agent" -m "..."
  ```
- Do **not** add `Co-Authored-By: Claude` trailers — the `-c` author override replaces that convention.
- Show the proposed message and wait for confirmation before committing.
- Never push unless I explicitly ask.

## Parallel subagent isolation

When two or more subagents are dispatched to operate concurrently on the same repository, every writing agent MUST run in an isolated git worktree. Concurrent writers on a shared working tree silently overwrite each other.

- **Preferred**: pass `isolation: "worktree"` on the Agent tool call. The harness auto-cleans the worktree if the agent makes no changes; on changes, the path + branch are returned and must be merged.
- **Alternative**: pre-create a worktree via `/using-git-worktrees create <branch>` and brief the subagent with its path as its working directory.
- **Exempt**: read-only agents (no Write/Edit in `tools:`) and sequential single-agent dispatch.

See [`docs/parallel-isolation.md`](docs/parallel-isolation.md) for the full rule, edge cases, and anti-patterns.

## Package managers

- For frontend and Node.js work, use only `pnpm` or `bun`.
- Never run or suggest `npm`, `npx`, or `yarn` for frontend work. Use `pnpm install`, `pnpm add`, `pnpm run`, `pnpm dlx`, or the matching `bun` / `bunx` command.
- When initializing a new frontend project, always ask which package manager to use: `pnpm` or `bun`.
- If an existing frontend project has only `package-lock.json` or `yarn.lock`, stop and ask whether to migrate to `pnpm` or `bun` instead of using npm/yarn.

## Things to never do

- Never add features I didn't ask for.
- Never rename variables or methods just to satisfy your preference.
- Never commit without being asked explicitly.
- Never push to remote without being asked explicitly.
- Never delete files without confirmation.
