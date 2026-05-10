# Preferences

Durable user / project preferences not visible from the code itself. Each entry has an ID of the form `P-YYYYMMDD-NN`. Remove entries that have been contradicted by a newer instruction.

---

### P-20260510-01 — Never invoke `speckit-git-*` skills
- **Date**: 2026-05-10
- **Preference**: Drive every commit, branch, and push from the `/git` skill / global commit rules in `~/.claude/CLAUDE.md`. Decline every `speckit-git-*` auto-execute prompt.
- **Why**: The `/git` skill enforces branch safety, conventional commit type, category tagging, agent authorship (`my@agent.commit`), and the refuse-on-main check. The spec-kit git extension does none of that.
- **Scope**: Project-wide. Already memorialised in user-level auto-memory.
- **Stale signal**: If the spec-kit git extension is replaced or gains the safety features above, re-evaluate.

### P-20260510-02 — Tasks.md phase headings carry an explicit verbose Status line
- **Date**: 2026-05-10
- **Preference**: Every `## Phase X: …` heading in `tasks.md` is immediately followed by `**Status**: ⬜🟡✅ (M/N — T###–T###)`. Recompute and rewrite the status line in the same edit that flips any task checkbox.
- **Why**: At-a-glance progress view. Drift between status and checkboxes makes future sessions read stale state.
- **Scope**: Spec-kit feature trees only.
- **Stale signal**: User says "skip the status line", or the convention is replaced.

### P-20260510-03 — Concise, code-first responses; no preamble
- **Date**: 2026-05-10
- **Preference**: Lead with code or the direct answer. Skip "Sure!", "Here's what I'll do", and end-of-message recaps. Bullet points over paragraphs for lists. Tables for any enumeration of three or more items.
- **Why**: User prefers signal over fluff. Codified in global `CLAUDE.md`.
- **Scope**: All communication.
- **Stale signal**: User starts asking for more context / explanation by default.

### P-20260510-04 — Prefer pnpm for Node.js operations
- **Date**: 2026-05-10
- **Preference**: `pnpm install`, `pnpm add`, `pnpm run`, `pnpm dlx`. Fall back to `npm` only when the project explicitly requires it (e.g. `.npmrc` with `engine-strict` and npm-only lockfile). Never suggest `yarn` unless the project already uses it.
- **Why**: Disk efficiency + monorepo support. Codified in global `CLAUDE.md`.
- **Scope**: All Node.js projects on this machine.
- **Stale signal**: User explicitly switches a project to npm/yarn.

### P-20260510-05 — Never edit `.env*` files; print copy-paste instructions instead
- **Date**: 2026-05-10
- **Preference**: When env file content is needed, provide exact copy-paste instructions and the content as a code block — do not write the file. Env files must be UTF-8 (not UTF-16/BOM). Only `.env.example` is ever committed.
- **Why**: Prevents accidental secret leaks via file-write tooling. Codified in global `CLAUDE.md`.
- **Scope**: All projects.
- **Stale signal**: User explicitly requests a write.
