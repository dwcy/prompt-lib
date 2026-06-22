# Evals

Post-task self-evaluation log. Each entry has an ID of the form `E-YYYYMMDD-NN` and is appended after a non-trivial task. Old evaluations can be removed once their lessons have been promoted to `lessons.md` / `mistakes.md`.

The evaluation questions:

1. Did I follow user constraints?
2. Did I make unverified assumptions?
3. Did I verify current facts when needed?
4. Did I produce the requested format?
5. What should be remembered? → new lessons / mistakes / preferences
6. What should be unlearned? → stale lessons to remove

---

### E-20260510-01 — Roll out parallel-subagent-isolation policy
- **Task**: `/plan` then implementation: 8 tasks ending in a v1.1.0 constitution amendment + canonical docs explainer + ADR.
- **Constraints followed?** Yes — single-track, no contract (no full-stack), template/skill/CLAUDE.md surfaces all touched, no force-push.
- **Unverified assumptions?** Assumed the Agent tool's `isolation: "worktree"` is the durable name of the parameter. Did not verify against a current harness release note — but it's named in the Agent tool description in this session, so the verification is implicit.
- **Verified current facts?** Read every target file before editing; confirmed `.specify/` structure, constitution version, template content.
- **Requested format?** Yes — task breakdown table, then sequenced edits, then commit + push.
- **To remember**:
  - L-20260511-01 (parallel isolation rule)
- **To unlearn**: nothing.

### E-20260510-02 — Branch + commit + push session work
- **Task**: Move all working-tree changes to `feat/parallel-subagent-isolation`, commit with agent authorship, push.
- **Constraints followed?** Mostly — agent authorship via `-c` flags ✓, no Co-Authored-By trailer ✓, push only because explicitly requested ✓. **One slip**: bundled unrelated WIP into the same `feat:` commit instead of splitting (see M-20260510-02).
- **Unverified assumptions?** Assumed `.todo/` was local-only when it was actually substantive backlog content the user wanted committed. Had to add a second commit when they redirected.
- **Verified current facts?** Yes — ran `git status --short`, `git ls-files`, `.gitignore` contents before staging.
- **Requested format?** Yes — proposed commit message in the conversation before running `git commit`.
- **To remember**:
  - M-20260510-01 (`-c` flag position on git commit)
  - M-20260510-02 (don't pollute `feat:` subjects with unrelated WIP)
  - M-20260510-03 (audit tracked-but-ignored files before any commit flow)
- **To unlearn**: nothing.
