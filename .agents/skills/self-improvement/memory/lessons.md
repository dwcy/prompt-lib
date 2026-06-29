# Lessons

Reusable rules learned from successes or general patterns in this project. Each entry has an ID of the form `L-YYYYMMDD-NN`. Remove entries that have become stale rather than leaving them with `**STALE**` markers — git history is the audit trail.

---

### L-20260510-01 — Verify current facts before quoting them
- **Date**: 2026-05-10
- **Situation**: User asked how a tool currently behaves; an answer drawn from memory could be months out of date.
- **Success**: Reading the actual file / running `--help` / consulting the live docs before quoting.
- **Root cause**: Training data is frozen; tools, APIs, prices, and CLI flags drift.
- **Future rule**: For any tool, API, model, library, or live product, verify with the current source (file on disk, `--help`, official docs, `claude mcp list`) before stating facts. Cite the verification.
- **Example**: Asked about MCP server health → run `claude mcp list` first, then quote the result.

### L-20260510-02 — Skill descriptions are the only thing that drives autonomous routing
- **Date**: 2026-05-10
- **Situation**: When two skills had similar descriptions, Claude picked the wrong one for a "commit this" request.
- **Success**: Rewriting descriptions to lead with the trigger phrase ("Use when…", "Use after…") and naming what the skill *does not* cover.
- **Root cause**: Claude only sees the `description:` field at routing time; the body is invisible to the matcher.
- **Future rule**: When adding or editing a skill, the first sentence of `description:` must name the trigger words and make the boundary against neighbouring skills explicit. Run `/review-conflicts` after.
- **Example**: `/commit` says "Lightweight quick commit — no branch safety, no agent authorship. For the full workflow use /git commit instead." That last clause is what prevents routing collision.

### L-20260511-01 — Parallel writing subagents must run in isolated worktrees
- **Date**: 2026-05-11
- **Situation**: Designing `/plan` Step 6 full-stack flow and `/speckit-implement` parallel batches that spawn two writing agents concurrently.
- **Success**: Pass `isolation: "worktree"` on the Agent tool call. The harness auto-cleans the worktree on no-change and returns the path + branch on changes.
- **Root cause**: Two writers on a shared working tree silently overwrite each other — git never sees the conflict because both writes are valid filesystem operations.
- **Future rule**: When dispatching ≥2 writing subagents concurrently, every concurrent writer gets `isolation: "worktree"`. Read-only auditors are exempt. Codified as Constitution Gate 6.
- **Example**: See [`docs/parallel-isolation.md`](../../../../docs/parallel-isolation.md) and ADR 0001.

### L-20260629-01 — Persisted cache schemas need legacy fixtures
- **Date**: 2026-06-29
- **Situation**: Added new env/tool metadata keys, then found the UI could crash when applying an older cached env snapshot before refresh.
- **Success**: Merge safe defaults into cached dictionaries before rendering and add a regression test with missing new keys.
- **Root cause**: Stale persisted cache data outlives code changes; fresh detection tests do not cover first-paint cache paths.
- **Future rule**: When adding keys to persisted cache payloads, test a legacy cache missing those keys.
- **Example**: `EnvPanel._apply_env()` tolerates cached env data without `uv` and database/editor keys.
