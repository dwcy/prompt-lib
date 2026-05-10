# Future Ideas Backlog

Opinionated backlog for future improvements to prompt-lib, the A2A bridge, and the orchestrator.

## P1 - High Leverage

### 1. Codex as an A2A Peer

Goal: make Codex another first-class A2A adapter, alongside Claude and Gemini.

Ideas:
- Add `services/a2a-bridge/src/a2a_bridge/adapters/codex/`.
- Implement `codex_command_factory(prompt)` and `parse_codex_event(event)`.
- Support both directions:
  - Claude delegates to Codex.
  - Orchestrator delegates PR review or implementation tasks to Codex.
- Add Agent Card skill metadata for Codex capabilities.
- Add real-CLI gated integration tests, similar to Gemini/Claude.
- Decide how Codex cwd, sandbox, approval mode, and model selection should map into A2A params.

Open questions:
- Should Codex receive raw prompts, structured task envelopes, or repo-aware instructions?
- Should Codex be allowed to edit files through A2A, or only return review/advice artifacts in v1?
- How should approvals and sandbox failures be surfaced over `task.state` / `task.artifact`?

### 2. Richer Statusline Runtime Data

Goal: make the statusline a quick operational dashboard without becoming noisy.

Ideas:
- Show whether the current repo is a normal worktree, linked git worktree, or detached/headless state.
- Show worktree name/path when inside an orchestrator-created worktree.
- Show dirty working tree summary:
  - staged count,
  - unstaged count,
  - untracked count,
  - conflicted count.
- Show active branch plus upstream ahead/behind count.
- Show active subagents currently working, if discoverable from Claude session logs or orchestrator state.
- Show active A2A tasks:
  - peer name,
  - task count,
  - oldest task age,
  - last terminal status.
- Add compact modes:
  - `minimal`,
  - `dev`,
  - `orchestrator`,
  - `debug`.
- Add a small cache layer so statusline stays fast and never blocks the prompt.

Open questions:
- Where is the best source of truth for subagent activity: session transcript, hook events, or explicit event log?
- Should statusline read orchestrator SQLite directly, or should the orchestrator expose a local status endpoint/file?

### 3. Support `AGENTS.md`

Goal: support the ecosystem convention where agent instructions live in `AGENTS.md`, while preserving existing `CLAUDE.md` behavior.

Ideas:
- Teach `@load-project` to detect and summarize `AGENTS.md`.
- Teach `@init-project` to optionally create `AGENTS.md`, `CLAUDE.md`, or both.
- Add precedence rules:
  - project `CLAUDE.md` for Claude-specific behavior,
  - `AGENTS.md` for shared agent conventions,
  - `.claude/` for local project commands/settings.
- Add installer/project-template support for `AGENTS.md`.
- Add a doctor check for drift between `CLAUDE.md` and `AGENTS.md`.
- Add docs explaining what belongs in each file.

Open questions:
- Should `AGENTS.md` be generated from `CLAUDE.md`, or should both be separate templates?
- Should shared rules be duplicated or imported?

### 4. Convert High-Value Skills to Folder-Based Agent Skills

Goal: move the most reusable slash commands from single markdown files into full skill folders with `SKILL.md`, `scripts/`, `references/`, and `assets/`.

Why this is useful:
- Keeps long instructions out of `SKILL.md` and moves stable background material into `references/`.
- Makes repeated mechanical work safer by putting validation and extraction logic in `scripts/`.
- Makes generated output more consistent by copying/filling templates from `assets/`.
- Makes skills easier to test because scripts can be run directly.
- Aligns the repo with the open Agent Skills folder format.

Suggested first conversions:
- `/skill-create` - highest leverage because it creates every future skill.
- `/git` and `/commit` - commit-message validation and staged diff classification are deterministic enough for scripts.
- `/pr` - PR bodies benefit from templates and automatic context collection.
- `/review` - severity rubrics and output templates reduce inconsistent review style.
- `/react-init` - scaffolding should use assets/templates instead of long inline instructions.
- `/react-test` - test skeleton generation and failure summarization are good script candidates.
- `/docs` - link checks, stale docs checks, and doc index generation fit scripts well.

Suggested structure:
```text
global/skills/<skill-name>/
  SKILL.md
  scripts/
    README.md
    .gitkeep
  references/
    README.md
    .gitkeep
  assets/
    README.md
    .gitkeep
```

Useful scripts to add:
- `validate_skill.py` - checks `SKILL.md` frontmatter, required folders, missing referenced files, and overly long instructions.
- `score_description.py` - checks whether a skill description includes both "what it does" and "when to use it".
- `frontmatter_validate.py` - reusable helper for skills, agents, rules, and output styles.
- `git_context.py` - shared helper for staged files, changed files, branch, merge base, and dirty counts.
- `markdown_lint_light.py` - validates headings, broken local links, duplicate titles, and unclosed fenced blocks.
- `template_fill.py` - tiny helper for replacing placeholders in assets.

Useful references to add:
- `skill-folder-format.md` - canonical folder layout and when to use scripts vs references vs assets.
- `description-trigger-rubric.md` - how to write descriptions that trigger reliably without being vague.
- `review-severity-rubric.md` - shared definitions for Critical / Warning / Suggestion.
- `conventional-commits.md` - commit type/scope/subject conventions.
- `docs-style-guide.md` - where to document things and how to keep docs short.
- `tanstack-boundaries.md` - Router vs Query vs Form vs Zustand state ownership.

Useful assets to add:
- `SKILL.md.tmpl` - base template for new folder-based skills.
- `commit-message.tmpl` - conventional commit template.
- `pr-body.tmpl.md` - consistent PR summary/test/risk template.
- `review-output.tmpl.md` - findings-first review output.
- `component.test.tsx.tmpl` - React Testing Library component test skeleton.
- `doc-page.tmpl.md` - docs page starter with purpose, usage, and maintenance notes.

Open questions:
- Should legacy `global/skills/*.md` coexist with folder skills, or should all global skills be migrated in one pass?
- Should shared helper scripts live under each skill, or in a repo-level `global/skills/_shared/` folder?
- Should `setup/apply.py` deploy both file-based and folder-based skills automatically?
- Should the `/docs` skill generate skill/agent indexes from folder metadata?

### 5. Implement a Symphony-Style Issue Tracker Orchestrator

Goal: evolve `services/orchestrator` from "watch PRs and review them" into a Symphony-style always-on coding-agent orchestrator where issues/tasks are the control plane.

Source inspiration:
- OpenAI Symphony article: `https://openai.com/index/open-source-codex-orchestration-symphony/`
- OpenAI harness engineering article: `https://openai.com/sv-SE/index/harness-engineering/`

Why this is useful:
- Removes the human bottleneck of manually opening and supervising agent sessions.
- Lets humans describe deliverables in an issue tracker and let agents pull/execute work.
- Supports long-running work that may create multiple PRs, investigation notes, videos, or follow-up tasks.
- Makes orchestration policy versioned in-repo through a `WORKFLOW.md` file instead of implicit human process.
- Gives the current orchestrator a path beyond PR review: implementation, refactor exploration, CI shepherding, docs gardening, and maintenance.

Core Symphony ideas to adopt:
- Issue tracker as the control plane.
- One isolated workspace per eligible issue.
- Bounded concurrency so the machine is busy but not overloaded.
- Single authoritative orchestration state for claims, retries, and reconciliation.
- Reconciliation before dispatch on every tick.
- Stall detection and retry for long-running or silent agents.
- Runtime behavior loaded from repo-owned `WORKFLOW.md`.
- Agent does ticket comments/state transitions/PR links using its normal tools, while the orchestrator schedules and observes.
- Explicit trust/safety posture for sandbox, approvals, write permissions, and merge authority.

Suggested architecture:
```text
services/orchestrator/src/orchestrator/
  workflow.py             # parse WORKFLOW.md frontmatter + prompt body
  trackers/
    base.py               # IssueTracker protocol
    linear.py             # Linear adapter first
    github_issues.py      # GitHub Issues fallback / later
  scheduler.py            # eligibility, claims, bounded concurrency
  runner.py               # launches A2A/Codex/Claude worker per issue
  reconciliation.py       # stale claims, state changes, stall detection
  workspace.py            # per-issue worktree/workspace lifecycle
  status.py               # statusline/dashboard-friendly snapshots
```

Potential `WORKFLOW.md` shape:
```markdown
---
tracker:
  kind: linear
  project: "ENG"
  active_states: ["Ready", "In Progress"]
  terminal_states: ["Done", "Canceled"]
concurrency:
  max_parallel: 3
agent:
  peer: codex
  timeout_minutes: 180
  stall_timeout_minutes: 20
workspace:
  mode: git-worktree
handoff:
  success_state: "Human Review"
  failure_state: "Needs Triage"
---

You are working one issue at a time.

1. Read the issue title, description, comments, linked PRs, and labels.
2. Create or reuse an isolated workspace for the issue.
3. Make progress until the issue reaches a clear handoff point.
4. Open PRs as needed.
5. Comment with what changed, how it was tested, and what needs human review.
6. If blocked, comment with the blocker and move the issue to the configured failure state.
```

Suggested state model:
```sql
CREATE TABLE issues (
    tracker_id TEXT PRIMARY KEY,
    tracker_kind TEXT NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL,
    updated_at TEXT,
    payload_json TEXT NOT NULL
);

CREATE TABLE claims (
    tracker_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    worker_pid INTEGER,
    workspace_path TEXT NOT NULL,
    last_event_at TEXT
);

CREATE TABLE retries (
    tracker_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    next_attempt_at TEXT NOT NULL,
    reason TEXT NOT NULL
);
```

Scheduler sketch:
```python
async def tick() -> None:
    workflow = workflow_loader.load()
    await reconciliation.reconcile(workflow)

    candidates = await tracker.list_eligible_issues(workflow.tracker)
    for issue in candidates:
        if scheduler.capacity_full():
            break
        if state.is_claimed(issue.id):
            continue
        if not retries.ready(issue.id):
            continue

        claim = state.claim(issue)
        workspace = await workspace_manager.prepare(issue)
        scheduler.start(run_issue(issue, claim, workspace, workflow))
```

Harness-engineering improvements to pair with Symphony:
- Make `AGENTS.md` a short map, not a giant manual; link to deeper `docs/` sources of truth.
- Add `docs/index.md`, `docs/architecture.md`, `docs/testing.md`, `docs/quality.md`, and `docs/operations.md` so agents know where to look.
- Add doc linting: broken links, stale references, missing owners, missing "last verified" metadata for generated docs.
- Make the app readable to agents:
  - per-worktree dev server,
  - Playwright/Chrome DevTools snapshots,
  - screenshots/videos attached to issue comments,
  - local logs/metrics/traces exposed through queryable files or APIs.
- Add structural linters and tests for architecture boundaries instead of only prose rules.
- Encode taste/invariants mechanically:
  - max file size,
  - allowed import directions,
  - schema/type naming conventions,
  - structured logging requirements,
  - test coverage expectations for changed modules.
- Treat agent failures as harness gaps: add docs, skills, guardrails, or scripts so the next run succeeds.

Suggested phases:
1. **Spec-only phase**: add `specs/003-symphony-orchestrator/` with `spec.md`, `plan.md`, `data-model.md`, `contracts/`, and `tasks.md`.
2. **Workflow loader phase**: parse `WORKFLOW.md` and validate config.
3. **Tracker abstraction phase**: add `IssueTracker` protocol and a fake tracker for deterministic tests.
4. **Workspace phase**: reuse/extend worktree manager for per-issue workspaces.
5. **Scheduler phase**: claims, bounded concurrency, retries, stall detection.
6. **Runner phase**: dispatch issue prompts over A2A to Claude/Codex.
7. **Status phase**: dashboard/statusline view of active issues, claims, stale runs, and last events.
8. **Harness phase**: doc map, architecture lint, Playwright evidence, log/metric capture.

Open questions:
- Start with Linear, GitHub Issues, or a local file-backed fake tracker?
- Should this replace PR polling or sit beside it as `orchestrator issue-serve`?
- Should the worker be A2A-only, Codex CLI-only, or capability-routed across peers?
- How much authority should agents have: comment only, open PRs, update issue state, push branches, or merge?
- Should restart recovery be SQLite-backed like current orchestrator or tracker/filesystem-driven like the Symphony spec?

## P2 - Orchestration Features

### Multi-Agent Run Graphs

Goal: let the orchestrator model a run as a graph of tasks, not one linear PR-review job.

Ideas:
- Represent steps like `plan`, `implement`, `test`, `review`, `summarize`.
- Store parent/child run relationships in SQLite.
- Show run graph in the Textual dashboard.
- Allow different peers per step: Claude for review, Codex for patching, Gemini for second opinion.
- Add per-step retry and timeout policies.

### Agent Capability Registry

Goal: route work based on declared capabilities instead of hardcoded peer names.

Ideas:
- Poll Agent Cards from known A2A peers.
- Cache peer capabilities in SQLite.
- Match tasks to peers by skills, model, cost, latency, write permission, and trust level.
- Add a CLI command: `orchestrator peers list`.

### Human-in-the-Loop Checkpoints

Goal: make autonomous runs pause cleanly when human judgment is needed.

Ideas:
- Add `run.needs_input` event type.
- Push ntfy notification with actionable context.
- Dashboard view for pending decisions.
- Resume runs after a human response.
- Support policies like "auto-review only" vs "patch and ask before commit".

### Worktree Lifecycle Improvements

Goal: make orchestrator-created worktrees safer and easier to inspect.

Ideas:
- Name worktrees with repo, PR, run id, and peer name.
- Write a small metadata file into each worktree.
- Add `orchestrator worktrees list/prune/open` commands.
- Add stale lock detection.
- Add "preserve failed worktree" mode for debugging.

### PR Review Quality Modes

Goal: make review behavior configurable by risk.

Ideas:
- `fast`: one agent, changed files only.
- `standard`: review diff plus nearby context.
- `deep`: multiple agents, tests/logs, architecture checks.
- `security`: include secret-auditor and dependency-sensitive checks.
- `frontend`: include screenshot/playwright checks when available.

### Scheduled Maintenance Runs

Goal: use the orchestrator for recurring repo health checks.

Ideas:
- Nightly dependency drift summary.
- Weekly stale branch/worktree cleanup.
- Test flake tracking from repeated failures.
- Docs freshness checks against known source files.
- Secret/gitignore audit before release.

## P3 - Developer Experience

### Better Docs Command

Goal: make docs easier to navigate and maintain.

Ideas:
- Add `/docs` skill to answer "where is this documented?"
- Add docs index generation from `docs/*.md`.
- Add doc freshness checks for agent names and skill names.
- Add "changed code but docs not updated" guardrails for common areas.

### Agent and Skill Linter

Goal: catch broken frontmatter, vague descriptions, stale tool lists, and routing overlap.

Ideas:
- Validate every `global/agents/*.md` has `name`, `description`, and `tools`.
- Flag descriptions that are too vague for autonomous routing.
- Detect two agents with highly overlapping trigger descriptions.
- Validate every documented agent exists on disk.
- Validate every documented skill exists on disk.

### Installer Improvements

Goal: make setup/apply safer and more transparent.

Ideas:
- Preview exact files to be copied with a diff view.
- Add a non-interactive `--check` mode for CI.
- Add `--component agents,skills,hooks` selection.
- Stop tracking generated `__pycache__` files.
- Add doctor output in JSON for automation.

### A2A Inspector / Debug Tools

Goal: make protocol debugging less painful.

Ideas:
- Add `a2a-bridge inspect <peer-url>` command.
- Show Agent Card, auth status, supported skills, and sample task run.
- Add SSE transcript capture to a file.
- Add replay tool for captured SSE streams.
- Add protocol conformance summary.

## P4 - Nice Later

### Cost and Latency Tracking

Ideas:
- Track per-peer task duration.
- Track token/cost estimates when available.
- Show slowest peers and common failure reasons.
- Route low-risk tasks to cheaper/faster peers.

### Notification Routing

Ideas:
- Different ntfy topics per repo.
- Escalation topic for failures and needs-input only.
- Quiet hours.
- Summary notifications for batch runs.

### Dashboard Enhancements

Ideas:
- Filter by repo, PR, peer, status, and run kind.
- Open artifact URL from selected row.
- Show live A2A stream for active task.
- Show worktree path and last git status.
- Add run detail pane with event timeline.

### Local Knowledge Index

Ideas:
- Index `docs/`, specs, agents, skills, and project templates.
- Add search command over local conventions.
- Let `@load-project` cite local docs by path.
- Surface stale docs when files they describe change.

## Architecture Sketches and Example Snippets

These are not final implementations. They are starting points for future specs.

### Codex A2A Adapter Structure

Suggested package layout:

```text
services/a2a-bridge/src/a2a_bridge/adapters/codex/
  __init__.py
  runner.py          # argv factory + stream parser
  server.py          # FastAPI app factory, Agent Card, JSON-RPC methods
  policy.py          # sandbox/approval/model mapping
```

Potential `runner.py` shape:

```python
from __future__ import annotations

import json
import shutil
from typing import Any

from a2a_bridge.protocol.tasks import Artifact


def codex_command_factory(prompt: str, *, cwd: str | None = None) -> list[str]:
    codex = shutil.which("codex") or "codex"
    argv = [
        codex,
        "exec",
        "--json",
        "--reasoning-effort",
        "medium",
        prompt,
    ]
    if cwd is not None:
        argv.extend(["--cwd", cwd])
    return argv


def parse_codex_event(event: dict[str, Any]) -> Artifact | None:
    kind = event.get("type")
    if kind == "assistant_message":
        text = event.get("text")
        if isinstance(text, str) and text:
            return Artifact(kind="text", mime_type="text/plain", content=text)

    if kind == "file_patch":
        return Artifact(
            kind="structured",
            mime_type="application/json",
            content={
                "path": event.get("path"),
                "summary": event.get("summary"),
            },
        )

    return None
```

Potential Agent Card skill:

```python
{
    "id": "codex-code-task",
    "name": "Codex code task",
    "description": "Run a repo-aware Codex task with optional file-edit capability.",
    "input_modes": ["text/plain", "text/markdown"],
    "output_modes": ["text/plain", "text/markdown"],
}
```

Policy questions to pin in the spec:
- `review_only`: Codex may inspect but not edit.
- `patch_allowed`: Codex may edit only inside the delegated worktree.
- `approval_required`: Codex may propose commands but must stop on sandbox/approval needs.
- `autonomous`: Codex can run tests and apply patches inside a disposable worktree.

### Statusline Data Architecture

Suggested architecture:

```text
global/statusline.py
  read fast cache file
  render compact prompt status

global/statusline/
  collectors/
    git.py              # branch, worktree, dirty counts, ahead/behind
    orchestrator.py     # active A2A runs from SQLite/status JSON
    subagents.py        # active Claude subagents from session metadata/logs
    docker.py           # existing Docker status
    tests.py            # last test status marker
  cache.py              # TTL cache helpers
  render.py             # mode-specific rendering
```

Cache file sketch:

```json
{
  "ts": "2026-05-10T21:20:00Z",
  "cwd": "C:/projects/prompt-lib",
  "git": {
    "branch": "main",
    "is_worktree": true,
    "worktree_name": "pr-42",
    "staged": 2,
    "unstaged": 4,
    "untracked": 1,
    "conflicted": 0,
    "ahead": 1,
    "behind": 0
  },
  "orchestrator": {
    "active_runs": 2,
    "active_peers": ["claude", "codex"],
    "oldest_run_seconds": 91
  },
  "subagents": {
    "active": ["python-tester", "tanstack-architect"]
  }
}
```

Provider interface sketch:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StatusChunk:
    key: str
    text: str
    severity: str = "info"


class StatusProvider(Protocol):
    name: str
    ttl_seconds: float

    def collect(self, cwd: str) -> StatusChunk | None:
        ...
```

Git dirty-count collector sketch:

```python
import subprocess


def git_counts(cwd: str) -> dict[str, int]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--branch"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=0.5,
        check=False,
    )

    counts = {"staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 0}
    for line in result.stdout.splitlines():
        if not line or line.startswith("##"):
            continue
        x = line[0]
        y = line[1]
        if line.startswith("??"):
            counts["untracked"] += 1
        elif x == "U" or y == "U" or (x, y) in {("A", "A"), ("D", "D")}:
            counts["conflicted"] += 1
        else:
            if x != " ":
                counts["staged"] += 1
            if y != " ":
                counts["unstaged"] += 1
    return counts
```

### `AGENTS.md` Support Structure

Suggested template:

````markdown
# AGENTS.md

Shared instructions for AI coding agents working in this repository.

## Project

- Name:
- Stack:
- Architecture:
- Main commands:

## Rules

- Preserve user changes.
- Run tests before final handoff when feasible.
- Keep changes scoped to the requested task.

## Specialist Routing

- React structure: `@react-architect`
- TanStack Router/Query/Form/Table: `@tanstack-architect`
- Python architecture: `@python-architect`
- Python tests: `@python-tester`
- Security/secret scan: `@secret-auditor`

## Commands

```bash
# install

# test

# lint

# run
```
````

Loader precedence sketch:

```python
def load_project_instructions(root: Path) -> dict[str, str]:
    docs = {}
    agents_md = root / "AGENTS.md"
    claude_md = root / "CLAUDE.md"

    if agents_md.exists():
        docs["shared_agents"] = agents_md.read_text(encoding="utf-8")
    if claude_md.exists():
        docs["claude_specific"] = claude_md.read_text(encoding="utf-8")

    return docs
```

Doctor check sketch:

```python
def instruction_drift(agents_text: str, claude_text: str) -> list[str]:
    findings: list[str] = []
    for heading in ["Project", "Commands", "Rules"]:
        if f"## {heading}" in agents_text and f"## {heading}" not in claude_text:
            findings.append(f"`CLAUDE.md` missing section also present in `AGENTS.md`: {heading}")
    return findings
```

### Orchestrator Run Graph Structure

Suggested data model:

```sql
CREATE TABLE run_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    graph_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    peer TEXT,
    state TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    payload_json TEXT NOT NULL
);

CREATE TABLE run_edges (
    graph_id TEXT NOT NULL,
    from_node_id TEXT NOT NULL,
    to_node_id TEXT NOT NULL,
    condition TEXT NOT NULL DEFAULT 'success'
);
```

Example graph:

```json
{
  "graph_id": "pr-42-review",
  "nodes": [
    { "id": "collect-diff", "kind": "gh.diff" },
    { "id": "review-claude", "kind": "agent.review", "peer": "claude" },
    { "id": "review-codex", "kind": "agent.review", "peer": "codex" },
    { "id": "synthesize", "kind": "agent.summarize", "peer": "claude" },
    { "id": "post", "kind": "gh.review.post" }
  ],
  "edges": [
    ["collect-diff", "review-claude"],
    ["collect-diff", "review-codex"],
    ["review-claude", "synthesize"],
    ["review-codex", "synthesize"],
    ["synthesize", "post"]
  ]
}
```

Executor sketch:

```python
async def run_graph(graph: RunGraph, router: PeerRouter) -> None:
    ready = graph.initial_nodes()
    completed: set[str] = set()

    while ready:
        batch = ready
        ready = []

        results = await asyncio.gather(
            *(run_node(node, router) for node in batch),
            return_exceptions=True,
        )

        for node, result in zip(batch, results, strict=True):
            if isinstance(result, Exception):
                await mark_failed(node, result)
                continue
            completed.add(node.id)
            ready.extend(graph.unblocked_children(node.id, completed))
```

### Capability-Based Peer Routing

Agent Card cache sketch:

```sql
CREATE TABLE peers (
    peer_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    name TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    skills_json TEXT NOT NULL
);
```

Routing sketch:

```python
def choose_peer(task: TaskSpec, peers: list[Peer]) -> Peer:
    candidates = [
        peer
        for peer in peers
        if task.required_skill in peer.skills
        and task.write_mode in peer.allowed_write_modes
    ]
    if not candidates:
        raise RuntimeError(f"no peer can handle {task.required_skill}")

    return sorted(
        candidates,
        key=lambda p: (
            p.current_load,
            p.median_latency_ms,
            p.cost_rank,
        ),
    )[0]
```

### A2A Inspector Command Shape

CLI sketch:

```bash
a2a-bridge inspect http://127.0.0.1:8765 \
  --token-env A2A_BEARER_TOKEN \
  --sample "Reply with pong"
```

Output sketch:

```text
Peer: claude-code-a2a-adapter
URL:  http://127.0.0.1:8765
Auth: ok

Skills:
- claude-prompt: Forward a user prompt to the Claude Code CLI and stream its output.

Sample task:
- submitted at 21:20:01
- working at 21:20:01
- artifact text/plain 4 chars
- completed at 21:20:03
```

Implementation sketch:

```python
async def inspect_peer(peer_url: str, token: str, sample: str) -> InspectResult:
    card = await fetch_agent_card(peer_url)
    client = DelegationClient(peer_url=peer_url, peer_bearer_token=token)

    events = []
    async with client:
        async for event in client.delegate(sample):
            events.append(event)

    return InspectResult(card=card, sample_events=events)
```
