# Feature Specification: Agent Eval & Regression Harness

**Feature Branch**: `019-agent-eval-harness`
**Created**: 2026-08-19
**Status**: Draft
**Input**: User description: "Eval/regression harness for agents, not a traditional LLM benchmark — test whether adding/changing skills, agents, prompts, hooks, and instructions actually improves coding results. Same tasks / same repo state, baseline config vs candidate config, run agent N times each, evaluate via code tests + LLM pairwise judge + agent metrics. Custom runner around git worktrees + tests + LLM judge, so Claude Code, Codex, Gemini CLI and different skill sets can be benchmarked on exactly the same tasks. Not SWE-bench."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A/B compare two configurations on a task set (Priority: P1)

As the maintainer of prompt-lib, after changing a skill, agent, hook, rule, or CLAUDE.md instruction, I run the harness with a baseline configuration and a candidate configuration against a fixed set of coding tasks. Each task starts from a pinned git state in an isolated worktree, the agent runs headlessly N times per configuration, and I get a side-by-side comparison that answers "did this change actually make the agent better?"

**Why this priority**: This is the entire point of the feature — every other capability (task authoring, judging, metrics) exists to serve this comparison. Without it the harness delivers no value.

**Independent Test**: Define one task and two configurations (candidate = baseline + one extra skill), run the harness with N=1, and verify per-run artifacts (`patch.diff`, `output.txt`, `metrics.json`) and a `comparison.json` are produced for the task.

**Acceptance Scenarios**:

1. **Given** a task set and two named configurations, **When** I invoke the harness run command, **Then** each task executes from its pinned git state in a fresh isolated worktree per run, for each configuration, N times.
2. **Given** a completed run matrix, **Then** results are stored per task/configuration/run with the produced diff, the agent's final output, and collected metrics.
3. **Given** a run where the agent fails or times out, **Then** the run is recorded as failed with the reason, and the remaining runs continue.
4. **Given** identical configuration content for baseline and candidate, **When** the harness runs, **Then** it warns that the comparison is a no-op but still executes.

---

### User Story 2 - Author tasks, rubrics, and configurations as versioned files (Priority: P2)

As the maintainer, I define eval tasks as markdown files (instructions + pinned start state + per-task checks), rubrics as markdown files, and configurations as named profiles, all under an `evals/` tree in the repo, so the benchmark itself is versioned and reviewable like any other source.

**Why this priority**: The harness can't run without tasks and configurations; file-based authoring is the enabler for US1 but is pure data definition, deliverable independently.

**Independent Test**: Create a task file and a config profile, run the harness's validate command, and verify it reports the task set and profiles as well-formed (or lists precise errors).

**Acceptance Scenarios**:

1. **Given** an `evals/tasks/` directory with task files, **When** I run the validate command, **Then** every task's required fields (id, prompt, start ref, checks) are verified and failures are reported with file and field.
2. **Given** a task pinned to a git ref that doesn't exist in the target repo, **Then** validation fails for that task with a clear message.
3. **Given** a configuration profile referencing a skill/agent file that doesn't exist, **Then** validation fails naming the missing file.

---

### User Story 3 - Deterministic code checks per run (Priority: P3)

As the maintainer, after each agent run the harness automatically executes the task's deterministic checks — tests pass/fail counts, build success, lint — plus repo-diff measurements (files changed vs files the task expected to change), and stores them in the run's metrics.

**Why this priority**: Deterministic checks are the cheapest, most trustworthy signal and must exist before LLM judging is meaningful.

**Independent Test**: Run one task whose check command is a test suite; verify `metrics.json` records test counts, build result, and unrequested-file-change count.

**Acceptance Scenarios**:

1. **Given** a task with a `checks` block (test/build/lint commands), **When** a run completes, **Then** each check's exit status and parsed counts are recorded in that run's metrics.
2. **Given** a task declaring an expected-files scope, **When** the agent changed files outside that scope, **Then** the count and list of unrequested changes are recorded.
3. **Given** a check command that hangs, **Then** it is killed at a configurable timeout and recorded as failed with reason `timeout`.

---

### User Story 4 - LLM pairwise judge with rubrics (Priority: P4)

As the maintainer, the harness pairs each baseline run's result with a candidate run's result for the same task and asks an LLM judge — primed with the task and selected rubrics — which implementation better satisfies the requirements, returning a winner, per-criterion notes, and a confidence score. Position bias is controlled by evaluating each pair in both A/B orders.

**Why this priority**: Pairwise judging captures quality dimensions deterministic checks can't, but is meaningless without US1's runs and US3's artifacts.

**Independent Test**: Feed two pre-recorded run artifacts for one task to the judge command and verify a `comparison.json` with winner, confidence, and per-criterion reasoning is produced.

**Acceptance Scenarios**:

1. **Given** completed baseline and candidate runs for a task, **When** judging executes, **Then** each pair is judged in both presentation orders and the verdict includes winner, confidence, and rubric-criterion breakdown.
2. **Given** the two orders disagree on the winner, **Then** the pair is recorded as a tie/inconclusive rather than silently picking one.
3. **Given** the judge model call fails, **Then** the comparison is marked `judge_error` and deterministic metrics still stand on their own.

---

### User Story 5 - Aggregate report across tasks and runs (Priority: P5)

As the maintainer, after a full matrix run I get a summary comparing the two configurations: task pass rate, test pass rate, unrequested changes, average tool calls, average tokens, average wall time, and pairwise win rate — as a terminal table and a persisted report file.

**Why this priority**: The aggregate is what actually answers the headline question, but it is a pure reduction over data produced by US1–US4.

**Independent Test**: Point the report command at a results directory from a prior run and verify the summary table renders with all metric rows and both configuration columns.

**Acceptance Scenarios**:

1. **Given** a completed results directory, **When** I run the report command, **Then** a baseline-vs-candidate table is printed and written to the results directory.
2. **Given** some runs failed, **Then** the report shows failure counts and excludes failed runs from quality averages while counting them against task pass rate.
3. **Given** N≥3 runs per cell, **Then** the report shows variance (min/max or stddev) for numeric metrics, not just means.

---

### User Story 6 - Multiple agent CLIs (Priority: P6)

As the maintainer, I can select which agent CLI executes the tasks (Claude Code first; Codex and Gemini CLI as additional adapters) so different agents and different configurations can be benchmarked on exactly the same tasks.

**Why this priority**: Valuable for cross-agent comparison but not needed to answer the primary "did my config change help?" question; Claude Code alone suffices for v1.

**Independent Test**: Run the same single task with the Claude Code adapter and a second adapter and verify both produce the same artifact schema.

**Acceptance Scenarios**:

1. **Given** a run invocation naming an adapter, **Then** the harness launches that CLI headlessly with the task prompt and the configuration profile applied.
2. **Given** an adapter that cannot report token counts, **Then** metrics record those fields as unavailable rather than zero.

### Edge Cases

- Agent modifies files outside the worktree (e.g., global `~/.claude/`): runs must be sandboxed to per-run config directories so a candidate profile cannot leak into the baseline runs or the user's real global config.
- Two runs execute concurrently: worktree isolation per run; results directories are per-run and never shared.
- The task's pinned ref becomes unreachable after history rewrite: validation catches it before the matrix starts, not mid-run.
- The agent produces no diff (gave up or answered in chat only): recorded as a completed run with an empty patch; deterministic checks still run; the judge is told the diff is empty.
- Interrupted matrix (Ctrl+C, machine sleep): results written incrementally per run; a rerun can resume, skipping completed cells.
- Judge self-preference bias (judging its own family's output): mitigated by both-orders judging and by keeping deterministic metrics primary in the report.
- Very large diffs exceeding judge context: diff is truncated per-file with a recorded truncation flag.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness MUST run a task matrix of (tasks × configurations × N repetitions), where N is configurable per invocation (default 3).
- **FR-002**: Every run MUST execute in a freshly created isolated git worktree checked out at the task's pinned ref, and the worktree MUST be removed after artifacts are collected.
- **FR-003**: Tasks MUST be defined as files under `evals/tasks/` containing at minimum: id, title, target repo, pinned start ref, agent prompt, check commands, and optional expected-file scope.
- **FR-004**: Configurations MUST be defined as named profiles under `evals/configs/` describing the exact agent-visible config (skills, agents, hooks, rules, instruction files) to apply for a run, applied per-run without touching the user's real global config.
- **FR-005**: The harness MUST launch the agent CLI headlessly (non-interactive), capture its final output and transcript, and enforce a per-run timeout.
- **FR-006**: After each run the harness MUST capture: the git diff (`patch.diff`), agent final output (`output.txt`), and `metrics.json` (check results, files changed, unrequested changes, tool calls, tokens, wall time, exit status).
- **FR-007**: Deterministic checks (test, build, lint commands from the task) MUST run after the agent finishes, each with its own timeout, and their outcomes recorded.
- **FR-008**: The harness MUST support pairwise LLM judging of baseline-vs-candidate run pairs per task using rubric files from `evals/rubrics/`, evaluating each pair in both orders and recording winner, confidence, and per-criterion notes in `comparison.json`.
- **FR-009**: The harness MUST produce an aggregate report (terminal table + persisted file) comparing configurations across: task pass rate, test pass rate, unrequested changes, architecture/rubric scores, average tool calls, average tokens, average time, pairwise win rate.
- **FR-010**: A validate command MUST verify tasks, rubrics, and config profiles are well-formed and that pinned refs and referenced files exist, before any matrix run.
- **FR-011**: Results MUST be written incrementally per run under a results directory (`evals/results/<run-id>/<task>/<config>/<n>/`), and a rerun MUST be able to resume an interrupted matrix by skipping completed cells.
- **FR-012**: Run failures (agent crash, timeout, check timeout, judge error) MUST be recorded with a machine-readable reason and MUST NOT abort the remaining matrix.
- **FR-013**: The agent CLI MUST be pluggable behind an adapter interface; v1 ships the Claude Code adapter, with the interface designed to admit Codex and Gemini CLI adapters without changes to the runner core.
- **FR-014**: The judge MUST be invokable standalone against previously recorded results (re-judge without re-running agents).
- **FR-015**: The harness MUST never push, commit to the user's branches, or modify the user's `~/.claude/`; all mutations are confined to worktrees, per-run config dirs, and the results directory.

### Key Entities

- **Task**: One benchmark unit — prompt, target repo, pinned start ref, checks, expected-file scope, rubric selection.
- **ConfigProfile**: A named, reproducible description of the agent-visible configuration (baseline, skills-v2, …).
- **Run**: One agent execution for a (task, profile, repetition) cell — artifacts + metrics + status.
- **CheckResult**: Outcome of one deterministic check within a run (kind, exit code, parsed counts, duration).
- **Comparison**: Pairwise judge verdict for a (task, baseline-run, candidate-run) pair — winner, confidence, criterion notes, order-agreement flag.
- **MatrixReport**: Aggregate across all cells for one harness invocation — per-metric config columns, variance, win rates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A config change's effect can be measured end-to-end (define candidate → run matrix → read report) without manual file juggling — one command per step.
- **SC-002**: Two consecutive matrix runs over the same inputs produce structurally identical artifacts (same schema, same file layout), enabling diffable regression history.
- **SC-003**: A 5-task × 2-config × 3-run matrix completes unattended, surviving at least one injected agent failure without losing the other cells.
- **SC-004**: The report answers "which config won?" with pairwise win rate plus at least 6 deterministic metric rows.
- **SC-005**: Zero writes outside worktrees/results/per-run config dirs during a matrix run (verifiable by inspecting the user's global config mtime and `git status` on the main tree).

## Assumptions

- The primary agent under test is Claude Code invoked headlessly via the `claude` CLI using existing subscription auth; per-run config isolation is achievable via CLI-supported mechanisms (settings flags / config-dir env / worktree-local `.claude/`). Exact mechanism is a plan-phase decision.
- The judge is an LLM reachable either through the same CLI (cheap, no API key) or an API key if configured; judge choice is a config value, not hardcoded.
- Tasks target real repos on this machine (prompt-lib itself or sibling projects); task authors are responsible for choosing stable pinned refs.
- Token/tool-call metrics come from the agent CLI's transcript/stream output where available; absent fields are recorded as unavailable.
- 3–5 repetitions is the expected N; the harness does not do statistical significance testing in v1 (variance display only).
- SWE-bench-style dataset import, CI integration, and a web dashboard are out of scope for v1.
