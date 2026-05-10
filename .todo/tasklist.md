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
