# Mistakes

Concrete failures from past sessions, recorded so they aren't repeated. Each entry has an ID of the form `M-YYYYMMDD-NN`. Remove entries that no longer apply.

---

### M-20260510-01 — Used `-c` after `commit` instead of before
- **Date**: 2026-05-10
- **Situation**: Tried to set agent authorship with `git commit -c user.email=... -c user.name=... -m "..."` and got `fatal: options '-m' and '-c' cannot be used together`.
- **Root cause**: `-c key=val` is a flag on the `git` program, not on the `commit` subcommand.
- **Future rule**: Always write `git -c user.email="my@agent.commit" -c user.name="Claude Agent" commit -m "..."`. Note the position: `-c` before `commit`.
- **Example**: See commit `0f73610` for the correct form.

### M-20260510-02 — Mixed user WIP into a feature-named commit without flagging it
- **Date**: 2026-05-10
- **Situation**: User asked to put "all changes" on a feature branch. Working tree contained both session work (parallel-isolation policy) and unrelated WIP (services/, statusline.py). Committed everything under a `feat:` subject line.
- **Root cause**: Took "all changes" too literally without sequencing the unrelated work into its own commit.
- **Future rule**: When a working tree contains unrelated changes and the user asks for "all changes" on a feature branch, group commits by concern: the headline feature gets the `feat:` commit, unrelated WIP gets a separate commit (`chore: include in-flight services WIP` or similar). Don't let an unrelated change pollute a `feat:` subject.
- **Example**: Should have been two commits: one `feat: enforce parallel subagent isolation…` and one `chore: ride along WIP from services/ and agents/`.

### M-20260511-01 — Raw string last line ended with backslash, breaking the closing delimiter
- **Date**: 2026-05-11
- **Situation**: Extended MASCOT ASCII art to full width using `__/  \` × 17 per row. The last row ended with `\`, immediately followed by the closing `"""`. Python's tokenizer treated `\"` as an escaped quote, leaving only `""` — not enough to close the triple-quoted string. The string ran on, consuming the LOGO definition as content. The error surfaced as `SyntaxError: invalid character '█'` on the LOGO line — far from the actual cause.
- **Root cause**: Python raw strings cannot end with an odd number of backslashes before the closing delimiter. `r"""...\"""` does not close at `\"`.
- **Future rule**: When generating multi-line raw strings containing `\` (ASCII art, regex patterns), verify the final line does not end with `\` before the closing `"""`. Adjust the last row so it ends with a non-backslash character (e.g. use `__/` instead of `__/  \`).
- **Example**: `r"""...__/"""` ✓ — `r"""...__/  \"""` ✗

### M-20260510-03 — Did not catch a tracked file matched by .gitignore
- **Date**: 2026-05-10
- **Situation**: Staged work and noticed `setup/__pycache__/apply.cpython-311.pyc` was tracked even though `.gitignore` covers `__pycache__/` and `*.pyc`.
- **Root cause**: `.gitignore` is advisory for *new* files. Files that are already tracked stay tracked until explicitly removed with `git rm --cached`.
- **Future rule**: At the start of any "let's commit this" flow, run `git ls-files | grep -E "__pycache__|\.pyc$|\.pyo$|\.DS_Store|Thumbs\.db"`. If anything matches, untrack it in a separate `chore:` commit before the feature commit.
- **Example**: See commit `b766600` for the correct cleanup.
