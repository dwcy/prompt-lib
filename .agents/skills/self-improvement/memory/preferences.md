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

### P-20260511-01 — Measure before stating; never guess a number when evidence is at hand
- **Date**: 2026-05-11
- **Preference**: When a concrete value (character count, line number, byte offset, version, etc.) can be obtained by reading what is directly in front of me — a file, a tool result, the conversation — do that first, then state the number. Never pattern-match to a familiar value and present it as fact.
- **Why**: I stated "~75 chars" from vague familiarity with terminal widths, then had to correct to 64 after actually counting. The guess wasted the user's time and required a correction.
- **Scope**: All responses. Applies especially to counts, sizes, offsets, and version numbers.
- **Stale signal**: N/A — this is a permanent epistemic standard.

### P-20260510-05 — Never edit `.env*` files; print copy-paste instructions instead
- **Date**: 2026-05-10
- **Preference**: When env file content is needed, provide exact copy-paste instructions and the content as a code block — do not write the file. Env files must be UTF-8 (not UTF-16/BOM). Only `.env.example` is ever committed.
- **Why**: Prevents accidental secret leaks via file-write tooling. Codified in global `CLAUDE.md`.
- **Scope**: All projects.
- **Stale signal**: User explicitly requests a write.

### P-20260618-01 — Keep installer prompts plain-language
- **Date**: 2026-06-18
- **Preference**: User-facing bootstrap prompts should say "Python" instead of exposing internal minimum versions like "Python 3.11 or newer"; keep version floors internal unless diagnosing a specific compatibility failure.
- **Why**: The user corrected the Python bootstrap copy as too technical/noisy.
- **Scope**: Setup launchers, install prompts, and user-facing setup docs.
- **Stale signal**: User asks to show explicit version requirements again.

### P-20260629-01 — Default Python support baseline is 3.14
- **Date**: 2026-06-29
- **Preference**: Treat Python 3.14 as the default supported Python line for new Cabal/package metadata, CI builds, runtime installer targets, and fast fake test environments.
- **Why**: User corrected "latest 3.x" to the explicit project baseline "3.14 from now on".
- **Scope**: Prompt-lib active package/runtime/build surfaces. Historical specs and unrelated compatibility examples can stay unchanged unless they drive behavior.
- **Stale signal**: User names a newer default baseline or asks to restore multi-version support.
