# Phase 0 Research: Agent Eval & Regression Harness

All `NEEDS CLARIFICATION` items from the Technical Context are resolved below. Each entry: Decision / Rationale / Alternatives considered.

## R1 — Runner: custom, not Promptfoo / LangSmith / SWE-bench

**Decision**: Build a small custom benchmark runner (`cabal.evals`) around git worktrees + deterministic checks + an LLM pairwise judge.

**Rationale**: The unit under test is *(agent CLI + repository state + configuration profile)*, not a prompt→completion pair. Promptfoo evaluates provider completions and cannot own worktree lifecycle, repo-diff metrics, or headless agent CLI orchestration without becoming a thin wrapper around exactly the code we'd write anyway. LangSmith adds a SaaS dependency and tracing model this repo doesn't need (results are local files, diffable in git). SWE-bench measures generic issue-solving on foreign repos; the question here is "did *my* config change improve results on *my* tasks", which requires custom tasks by definition. This matches the user's own conclusion in the feature input.

**Alternatives considered**: Promptfoo (rejected: prompt-level, not agent-level; Node dependency in a Python repo); LangSmith (rejected: SaaS, API-key-centric, overkill for local regression history); SWE-bench (rejected: wrong population of tasks, heavyweight harness).

## R2 — Configuration isolation mechanism

**Decision**: For each run, materialize the config profile into a scratch directory and launch the agent with `CLAUDE_CONFIG_DIR=<scratch>/config`. The profile overlay supplies `CLAUDE.md`, `settings.json`, `skills/`, `agents/`, etc. Project-scoped config (`.claude/` inside the worktree) is also supported as part of the overlay since the worktree is disposable. `--settings <file>` may additionally be passed when a profile only tweaks settings.

**Rationale**: `CLAUDE_CONFIG_DIR` relocates the entire user-level config root, giving hermetic isolation: the baseline run cannot see the candidate's skills, and neither can touch the real `~/.claude/` (FR-004, FR-015, SC-005). Materializing per run (not per profile) means a crashed run can't poison the next one, and profiles remain declarative files in git.

**Alternatives considered**: Deploying profiles into the real `~/.claude/` between runs via the apply wizard (rejected: mutates user global state — forbidden by FR-015 and constitution Principle IV's spirit); only worktree-local `.claude/` (rejected: cannot remove user-global skills/instructions from the baseline, so profiles wouldn't be hermetic); containerizing runs (rejected: heavyweight, Windows friction, subscription CLI auth complications).

**Validation note — RESOLVED (T010, 2026-08-19)**: live-verified on this machine. `CLAUDE_CONFIG_DIR` relocation is honored: with an empty scratch config dir, `claude -p … --output-format json` returns `is_error: true` with `result: "Not logged in · Please run /login"` (exit 1, machine-detectable JSON — useful for adapter failure classification). Auth material does NOT resolve from the real `~/.claude/` when the config dir is relocated, so the credential-copy fallback is REQUIRED, not optional: `profile.py` MUST copy `~/.claude/.credentials.json` into every scratch config dir it materializes, and the scratch dir MUST be deleted after the run (credentials never persist in results). CLAUDE.md/skills pickup under relocation is verified end-to-end in the quickstart smoke (T031) via a marker-instruction profile.

## R3 — Headless agent invocation

**Decision**: One-shot invocation per run: `claude -p "<task prompt>" --output-format stream-json --verbose --permission-mode acceptEdits` with `cwd` = the run's worktree, per-run timeout (default 15 min) enforced by the harness, stdout captured to `transcript.jsonl`, final `result` event's text to `output.txt`.

**Rationale**: Each repetition must be an independent cold trial — reusing a persistent session (dotnetgen's `ClaudeSession`) would share context between repetitions and corrupt the measurement. `stream-json` is required anyway for tool-call/token metrics (R5). `acceptEdits` lets the agent edit files in the disposable worktree without interactive prompts while still blocking arbitrary destructive commands; the worktree is the blast radius.

**Alternatives considered**: persistent stream-json session per config (rejected: cross-run contamination); `--output-format json` (rejected: loses per-event tool-call data); `--dangerously-skip-permissions` (rejected as default: broader blast radius than needed; can be opted into per task via `task.toml` for tasks that require shell-heavy work, recorded in metrics).

## R4 — Worktree lifecycle and diff collection

**Decision**: `git -C <repo> worktree add --detach <scratch>/wt <ref>` before the run; after the run `git -C <wt> add -N .` then `git -C <wt> diff` → `patch.diff` plus `git -C <wt> status --porcelain` → changed-file list; finally `git -C <wt> worktree remove --force` (fallback: `rm -rf` + `git worktree prune`).

**Rationale**: Detached checkout avoids branch creation/cleanup entirely — no named branches, nothing to collide with the user's branches (FR-015). `add -N` makes untracked new files appear in the diff without staging content. Forced removal is safe because every artifact is copied out first.

**Alternatives considered**: `git clone` per run (rejected: slower, duplicates object store); `git stash`-based reset of a shared checkout (rejected: single shared tree serializes runs and risks cross-run leakage); named branches per run (rejected: pollutes branch list, needless).

## R5 — Metrics extraction

**Decision**: Parse the captured `transcript.jsonl`: tool calls = count of `tool_use` content blocks across assistant events (also bucketed per tool name); tokens/cost/turn-count from the terminal `result` event, normalized the same way as `cabal.dotnetgen.providers.usage.parse_usage` (absent fields recorded as `null`, never zero); wall time measured by the harness clock around the subprocess. Deterministic check results, diff stats, and unrequested-change counts are merged into the same `metrics.json`.

**Rationale**: The stream-json schema is already understood and partially parsed in this repo (`dotnetgen/providers/cli_shell.py`, `usage.py`) — the harness reuses that knowledge and its "report absence, don't fake zero" convention (spec assumption + FR-006). Contract tests pin the parser against recorded fixture transcripts so CLI schema drift is caught loudly.

**Alternatives considered**: scraping `~/.claude` session files (rejected: config dir is relocated per run and the format is less stable than the documented stream-json); OpenTelemetry hooks (rejected: v1 overkill).

## R6 — Pairwise judge design

**Decision**: Judge = one-shot `claude -p` call (model configurable in `eval.config.toml`, default a cheap/fast model) with a prompt containing: task prompt, selected rubric files, both candidates' `patch.diff` (per-file truncation with recorded flag) + `output.txt` + deterministic check summaries, and an instruction to answer *only* with JSON matching the verdict schema (winner A|B|tie, confidence 0–1, per-criterion notes). Every pair is judged twice with A/B swapped; if the orders disagree on the winner the pair is recorded as `tie` with `order_agreement: false`. Pairing: repetition i of baseline vs repetition i of candidate. `judge` is a standalone subcommand usable against previously recorded results (FR-014).

**Rationale**: Both-orders judging is the standard mitigation for position bias; disagreement→tie keeps false positives out of the win rate. Shelling the CLI keeps v1 free of API keys (spec assumption). Keeping the judge independent from `dotnetgen`'s provider stack avoids coupling two features' internals; only the small usage-normalization idea is shared.

**Alternatives considered**: absolute 0–10 scoring per run (rejected: less reliable than pairwise, per the feature input); reusing `dotnetgen.providers` classes directly (rejected: `StageBinding`/pipeline-shaped API, would couple 019's core to 018's internals; revisit extraction to a shared module only when a third consumer appears); majority vote of 3 judges (deferred: config knob `judge.votes` can be added later without schema changes).

## R7 — Definition file formats

**Decision**: TOML for structured definitions (`task.toml`, `profile.toml`, `eval.config.toml`) parsed with stdlib `tomllib`; markdown for prose (task `prompt.md`, `rubrics/*.md`). A task is a directory `evals/tasks/<id>/`; a config profile is a directory `evals/configs/<name>/` containing `profile.toml` plus the overlay files it references.

**Rationale**: Zero new runtime dependencies (PyYAML is not in `pyproject.toml`; adding it for frontmatter alone is not justified). TOML is stdlib-parseable in Python 3.11+, comment-friendly, and diff-friendly. Directory-per-task cleanly separates the prompt (markdown, long) from the machine-read fields.

**Alternatives considered**: YAML frontmatter in one markdown file per task (rejected: requires PyYAML); JSON (rejected: no comments, hostile to hand-authoring); pure markdown with conventions (rejected: fragile parsing).

## R8 — Agent adapter interface

**Decision**: `adapters/base.py` defines an `AgentAdapter` protocol: `run(prompt, worktree, config_dir, timeout) -> AgentRunResult` (final text, transcript path, exit status, failure reason) and `capabilities()` (which metric fields it can supply). v1 ships only `claude_code.py`. Metrics fields an adapter can't supply are `null` ("unavailable"), satisfying US6's acceptance scenario 2 ahead of time.

**Rationale**: FR-013 requires the seam now so Codex/Gemini adapters (US6, P6) drop in without touching runner core. The codex one-shot pattern already proven in `dotnetgen/providers/cli_shell.py` shows the adapter shape works for non-Claude CLIs.

**Alternatives considered**: hardcoding `claude` in the runner (rejected: violates FR-013); building all three adapters in v1 (rejected: P6 priority, YAGNI).

## R9 — Results layout, resume, and report

**Decision**: `evals/results/<run-id>/` where run-id is caller-supplied or derived from timestamp at CLI entry. Cell path `<task>/<config>/<n>/` holds `patch.diff`, `output.txt`, `transcript.jsonl`, `metrics.json`, written atomically (`.tmp` + rename) at cell completion; a cell with a valid `metrics.json` is "complete" and is skipped on resume (`run --resume <run-id>`). `comparison.json` per task; `report.json` + `report.md` (rich-rendered table also printed to terminal) at the root. `evals/results/` added to `.gitignore`.

**Rationale**: Incremental atomic writes give FR-011/FR-012 (interruption survival, failure isolation) with no database. Files are diffable and portable; SC-002's schema stability is enforced by the JSON Schemas in `contracts/`.

**Alternatives considered**: SQLite results store (rejected for v1: adds query power nobody asked for; JSON files satisfy every FR); committing results to git (rejected: churn; reports can be manually promoted into docs if wanted).

## R10 — Deterministic checks & unrequested-change measurement

**Decision**: `task.toml` declares ordered checks: `[[checks]]` entries with `kind` (`test`|`build`|`lint`|`custom`), `cmd` (argv list), optional `parser` (`pytest`|`dotnet`|`exit-code`, default `exit-code`), each run in the worktree with its own timeout (default 5 min). Parsed counts (passed/failed) extracted for known parsers; otherwise pass/fail from exit code. `expected_files` (glob list) in `task.toml` defines the change scope; changed files outside it are counted+listed as `unrequested_changes`.

**Rationale**: Exit-code default keeps task authoring trivial; pytest/dotnet parsers cover this machine's actual stacks. Scope-by-glob directly implements the "unrequested changes" metric from the feature input.

**Alternatives considered**: language auto-detection of check commands (rejected: implicit magic, tasks should pin their own commands); AST-based complexity metrics (deferred: the input lists complexity as a metric, but no reliable cross-language measure fits v1 — rubric criteria cover it qualitatively; revisit with radon/similar for Python-only tasks later).
