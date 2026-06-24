---
name: self-improvement
description: Invoke proactively after any user correction ("no", "don't", "wrong", "stop doing X") or after fixing a non-obvious bug. Also invoke when the user asks to improve future performance, review prior work, learn from mistakes, or maintain project memory. Captures lessons into .Codex/skills/self-improvement/memory/. Never claims retraining of model weights.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

## Core rule

You cannot retrain yourself. You improve by maintaining **reusable structured context**:

- **lessons** — what worked, what didn't, and the rule going forward
- **mistakes** — concrete failures so they aren't repeated
- **preferences** — durable user / project preferences not visible from code
- **evals** — checklists run after important tasks

If you ever feel tempted to write "I've learned X" without writing a memory entry — the learning is ephemeral and lost. Write it down.

## When to invoke

The user explicitly asks: *"remember that…"*, *"learn from this"*, *"don't do that again"*, *"save this as a preference"*, *"add a lesson"*, *"forget X"*, *"that's no longer true"*, *"review what we did"*.

You should also invoke proactively after:

- A user correction (*"no, don't do X"*, *"stop doing Y"*, *"actually Z worked"*).
- A non-obvious success you discovered through trial-and-error.
- Finishing a non-trivial task (run the self-evaluation in `memory/evals.md`).
- Discovering something about how the code works that wasn't obvious from a quick read.

## Memory files

Stored at `.Codex/skills/self-improvement/memory/`:

| File | Holds | When to update |
|---|---|---|
| `lessons.md` | Reusable rules learned from successes or general patterns | After verifying a pattern works ≥2 times, or after a clear single success worth keeping |
| `mistakes.md` | Specific failures + root cause + what to do instead | Immediately after a correction or failure |
| `preferences.md` | Durable user/project preferences (tone, tooling, layout) | When the user states a preference that is project-wide and durable |
| `evals.md` | Post-task self-evaluation checklist | Append after every significant task |

## Workflow

### 1. Review history (when invoked)

Look back at the current and recent conversations. Identify:

- User corrections — "no", "don't", "stop", "actually", "wrong"
- Failed assumptions you made that the user had to fix
- Patterns that succeeded after multiple attempts
- Things the user clarified about the codebase or their preferences

Separate **facts** (the user said this; the test passed) from **guesses** (probably this is why; I think they want this).

Never store sensitive information (tokens, secrets, internal credentials) — even if the user mentioned them in passing.

### 2. Extract lessons

Use the lesson template for every entry. Every lesson has a unique ID — `L-YYYYMMDD-NN` for lessons, `M-YYYYMMDD-NN` for mistakes, `P-YYYYMMDD-NN` for preferences, `E-YYYYMMDD-NN` for eval runs. IDs let you reference and remove specific entries later.

```markdown
### L-20260511-01 — Short imperative title
- **Date**: 2026-05-11
- **Situation**: What was happening when the lesson surfaced.
- **Mistake or success**: What went wrong, or what worked.
- **Root cause**: Why it happened.
- **Future rule**: One-line rule going forward.
- **Example**: Concrete demonstration of the correct behaviour.
```

### 3. Update memory

Append the entry to the appropriate file. Keep entries concise. If you find yourself writing more than ~8 lines, you're explaining too much — link to a doc or a commit instead.

### 4. Before future tasks

At the start of any non-trivial task, **read the four memory files**. Treat the entries as guidance, not absolute truth:

- If a lesson conflicts with the current user instruction → **follow the current user**, then run the stale-detection check below.
- If a lesson seems stale (the tool/API/code it references no longer matches reality) → run the stale-detection check.

### 5. Stale lesson detection + removal (CRITICAL)

Memory is not forever. The world changes — a tool that was broken last week may work today, a preference may shift, a constraint may be lifted. The skill must be able to **unlearn**.

Triggers that suggest a lesson is stale:

| Trigger | Action |
|---|---|
| User asks for something a stored lesson said never to do | Verify it works *now*; if yes, remove the lesson |
| A tool that a lesson said "always fails" succeeds without error | Remove the lesson |
| User explicitly says "actually, X works now" / "ignore that old rule" | Remove the matching lesson immediately |
| A preference is contradicted by a new explicit instruction | Update or remove the preference |
| The code path a lesson described has been refactored away | Remove the lesson; the citation is broken |

**How to remove**: use `Edit` to delete the entry from the memory file, or run `python scripts/extract_lessons.py remove <file> <id>`. Always print which entry you removed and why, so the user can object if you removed something they wanted to keep.

**Do not soft-delete by adding `**STALE**` markers.** Memory files should reflect current truth. Audit trail lives in git history.

### 6. Post-task evaluation

After completing a non-trivial task, append one entry to `memory/evals.md`:

```markdown
### E-20260511-01 — Task title
- Did I follow user constraints? (yes/no — what missed)
- Did I make unverified assumptions? (yes/no — which)
- Did I verify current facts when needed? (yes/no)
- Did I produce the requested format? (yes/no)
- What should be remembered? → New lesson IDs added: L-…, M-…
- What should be unlearned? → Removed lesson IDs: L-…
```

## Helper script

`scripts/extract_lessons.py` provides three commands:

```bash
python .Codex/skills/self-improvement/scripts/extract_lessons.py list [<file>]
# Lists all entry IDs + titles in lessons/mistakes/preferences/evals.

python .Codex/skills/self-improvement/scripts/extract_lessons.py remove <file> <id>
# Removes a specific entry by ID. Prints the removed block to stderr so you can paste it back if needed.

python .Codex/skills/self-improvement/scripts/extract_lessons.py validate
# Checks that every entry has the required fields and a unique ID. Exit 1 on malformed memory.
```

`<file>` is `lessons`, `mistakes`, `preferences`, or `evals` (no extension).

Direct `Edit` on the memory files is always allowed; the script is a convenience for IDs and validation.

## Anti-patterns

- **Storing rumours.** "User seems annoyed" is not a lesson. "User explicitly asked for X" is.
- **Storing what the code already shows.** If a future Codex can grep the repo and find the answer, don't store it.
- **Vague rules.** "Be more careful" is useless. "Run `pnpm test` before claiming a PR is ready" is a rule.
- **Storing secrets.** API keys, tokens, internal URLs — never. Even hashed.
- **Soft-deleting stale lessons with markers.** Delete them. Git history is the audit trail.
- **Treating memory as authority.** Current user instructions override memory. Always.

## Examples

See `memory/lessons.md`, `memory/mistakes.md`, `memory/preferences.md`, and `memory/evals.md` for working examples in the canonical format.
