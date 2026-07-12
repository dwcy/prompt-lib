---
name: change-summary
description: Summarizes a diff, branch, or PR as a plain-language "file changed + why" report grouped into categories — explains the reasoning behind each change, not just what moved, written so a non-expert can follow it without opening the diff. Use whenever the user asks "give me a table of what changed and why", "summarize the changes with reasons", "files changed and reason", "explain this diff/PR in plain language", "what did we change and why", or wants a reviewable change-log distinct from raw git/gh output.
allowed-tools: Bash(git *), Bash(gh *), Read
context: fork
agent: Explore
---

Turn a set of changes into a report someone could read cold — no familiarity with the codebase, the conversation that produced the changes, or git jargon required. The value isn't restating the diff; it's explaining, in plain words, what happened and *why it needed to happen*.

This runs in an isolated read-only subagent (`context: fork` + `agent: Explore`) so the raw git/gh output collected along the way never lands in the main conversation — only the finished report does.

## Step 1 — Resolve the scope

Figure out what set of changes to summarize, in this priority order:

1. **User named a PR** ("PR #69", "this PR", "the last PR") → pass `--pr <number>`. If they said "this PR" without a number, try `gh pr view` with no args first (current branch) before asking.
2. **User named a branch or commit range** ("compare against main", "since the last release") → pass `--base <ref>` (and `--head <ref>` if they also named a head other than the current one).
3. **User said "staged" / "what I'm about to commit"** → pass `--staged`.
4. **Nothing specified** → run the script with no flags; it auto-detects in this order: staged changes, then unstaged changes, then an open PR for the current branch, then a diff against the merge-base with `main`/`master`.

Only ask the user if the request is genuinely ambiguous (e.g. they mention two different PRs, or a range that doesn't resolve). Don't ask just because a flag wasn't given — the auto-detect order above is the sensible default.

## Step 2 — Collect the facts

```bash
python scripts/collect_change_scope.py [--pr <number>] [--base <ref>] [--head <ref>] [--staged]
```

This prints JSON: `scope` (what was diffed and how), `files` (status + path for every changed file), `commits` (hash/subject/body for the resolved range, empty for working-tree diffs), and `pr` (title/body, or `null`). It exists so the git/gh-wrangling — figuring out refs, handling a missing `gh` auth, Windows git resolution — happens once, deterministically, instead of being re-derived by hand every time.

If `scope.kind` comes back `"none"` or `"error"`, say so plainly and stop — don't invent a table for changes that don't exist.

## Step 3 — Gather the "why" behind each file

The script's output is raw material, not the report. For each changed file, figure out the actual reason it changed, in this order of preference:

1. **Conversation context** — if these changes were just made in this session (or are visible earlier in the transcript), the reasoning already spoken aloud is almost always richer and more accurate than any commit message. Prefer it.
2. **Commit messages/bodies and PR body** from the script's output — these usually state intent, especially in this project where commit subjects follow `<type>: <subject>`.
3. **The diff itself** — for anything still unclear, read the actual change (`git diff <base>...<head> -- <path>`, or `Read` the file) and infer intent from what changed. If you're inferring rather than quoting a stated reason, don't dress it up as certain — state the mechanical change plainly and be honest that the reasoning is inferred.

Never fabricate a motivation you can't support from one of the three sources above.

## Step 4 — Group into categories that fit what actually changed

Don't force a fixed taxonomy (no hardcoded "docs / code / tests" template) — let categories emerge from the actual files, e.g. by directory or shared purpose. See [`references/category-heuristics.md`](references/category-heuristics.md) for how to draw the lines, including when a single table with no grouping is the right call (small or single-purpose diffs).

## Step 5 — Write each row

- Plain language. Spell out any project-specific or internal term the first time it appears — assume the reader has never seen this codebase's jargon (e.g. don't say "the wrapper" without saying what it wraps and why it exists).
- Explain both halves: *what* changed mechanically, and *why* — what problem it fixes, what contradiction it resolves, or what it was blocking.
- **Collapse identical reasoning into one row.** If ten files changed for the exact same reason (a batch rename, a shared pin removed), list them together in one `File` cell separated by commas — never repeat the same sentence ten times.
- If a file was deleted, say so explicitly in the reason ("deleted — ...").

Follow the structure in [`assets/report-template.md`](assets/report-template.md): one `##` header per category, then a `File | Reason` table.

## Edge cases

- **No changes in the resolved scope** — report that plainly instead of producing an empty or fabricated table.
- **`gh` unavailable or not authenticated** — fall back to git-only info and mention once, briefly, that PR context wasn't available (don't fail the whole report over it).
- **Huge diff (100+ files, e.g. a lockfile or generated output)** — it's fine to summarize a repetitive bucket as one row ("38 files under `dist/` — build output, regenerated automatically") rather than listing each one.

See [`references/example-output.md`](references/example-output.md) for the target depth and tone — that's the bar to match, not exceed with padding or fall short of with mechanical one-liners.
