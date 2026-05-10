# Quickstart — Agent Orchestrator (v1)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Date**: 2026-05-10

End-to-end: from a fresh clone of `prompt-lib` to a posted PR review on a throwaway repo, in under 10 minutes (SC-004).

This is also the manual verification flow for v1. Every numbered step maps to a Success Criterion or Acceptance Scenario; failures here block release.

---

## Prerequisites

You need these before starting. The orchestrator does NOT install them.

- **Python 3.13+** with `uv` on PATH.
- **`gh` CLI** authenticated to GitHub (`gh auth status` shows logged in).
- **A throwaway test GitHub repo** you own (or where you have review-comment permission). Don't use a real production repo for v1 verification.
- **The `services/a2a-bridge/` package built** (see `specs/001-a2a-bridge/quickstart.md`).
- **A phone with the [ntfy app](https://ntfy.sh/app)** installed (iOS or Android).

---

## 1. Pick a topic and subscribe your phone

ntfy topics are global on the public server. Treat the topic name as a low-grade secret — anyone who knows it can publish or subscribe.

Generate a hard-to-guess topic (any random string works):

**PowerShell:**
```powershell
[guid]::NewGuid().ToString('N')
```

**bash / zsh:**
```bash
uuidgen | tr -d - | tr 'A-Z' 'a-z'
```

Open the ntfy app on your phone → "Subscribe to topic" → paste the string. Tap the bell to confirm subscriptions are enabled.

Verify the subscription works without the orchestrator:

```bash
curl -d "hello from quickstart" "https://ntfy.sh/<your-topic>"
```

You should see a notification on your phone within a couple of seconds. If not, fix this before continuing — the orchestrator can't help you here.

---

## 2. Set environment variables (no `.env` files)

Per CLAUDE.md, the orchestrator does NOT read or write `.env` files. Set these in your current shell only — they don't need to persist across sessions for this verification.

**PowerShell:**

```powershell
$env:ORCHESTRATOR_REPO         = 'YOUR_GITHUB_USER/your-test-repo'
$env:ORCHESTRATOR_NTFY_TOPIC   = '<your-topic>'
$env:ORCHESTRATOR_POLL_SECONDS = '30'
$env:A2A_PEER_URL              = 'http://127.0.0.1:8765'
$env:A2A_BEARER_TOKEN          = '<your-a2a-bearer-token>'
```

**bash / zsh:**

```bash
export ORCHESTRATOR_REPO='YOUR_GITHUB_USER/your-test-repo'
export ORCHESTRATOR_NTFY_TOPIC='<your-topic>'
export ORCHESTRATOR_POLL_SECONDS=30
export A2A_PEER_URL='http://127.0.0.1:8765'
export A2A_BEARER_TOKEN='<your-a2a-bearer-token>'
```

`A2A_BEARER_TOKEN` must match the token you started the A2A bridge with (Step 3). The orchestrator validates it on first delegate call.

---

## 3. Terminal 1 — start the A2A Claude adapter

The orchestrator delegates each PR review to a peer Claude Code agent reachable via the A2A bridge. Start the bridge first:

```bash
cd services/a2a-bridge
uv run a2a-bridge serve claude
```

You should see uvicorn bind to `127.0.0.1:8765`. Leave this running.

---

## 4. Terminal 2 — start the orchestrator daemon

```bash
cd services/orchestrator
uv run orchestrator serve
```

You should see:

```
[orchestrator] config OK · repo=YOUR_GITHUB_USER/your-test-repo poll=30s db=~/.claude/orchestrator/events.db
[orchestrator] schema bootstrapped · WAL enabled
[orchestrator] gh auth OK · ntfy reachable · a2a peer reachable
[orchestrator] polling loop started
```

Leave this running. If any of those checks fail, the daemon exits with a non-zero status and the failure reason — fix the failing one (`gh auth login`, restart the bridge, etc.).

---

## 5. Terminal 3 — start the dashboard

```bash
cd services/orchestrator
uv run orchestrator dash
```

You should see a Textual TUI:

- A gradient banner identifying the orchestrator and the watched repo
- An empty `Recent runs` table
- An empty event tail
- A status footer showing `connected · 0 events · last poll: never`

Leave this running.

---

## 6. Trigger a PR review

In a fourth terminal, in your throwaway test repo:

```bash
git checkout -b quickstart-test
echo "verification" > QUICKSTART.txt
git add QUICKSTART.txt
git commit -m "test: orchestrator quickstart"
git push -u origin quickstart-test
gh pr create --title "Quickstart test" --body "Verifying orchestrator v1 end-to-end"
```

Note the PR number printed by `gh pr create`.

---

## 7. Verify the end-to-end flow (≤ 35 s wall-clock)

Within one polling interval (~30 s) plus a few seconds of agent dispatch:

| Where | What you should see |
|---|---|
| **Phone** | Info-level ntfy notification: title `Reviewing PR #N`, body `<repo> · <head_sha[:7]>`. |
| **Dashboard runs table** | A new row appears with state `running`, the PR number, and the head SHA. |
| **Dashboard event tail** | A stream of `agent.message` and `agent.state` events as the peer agent works. |
| **Daemon log** | `run.started run_id=…`, then a series of streaming events. |

Within ~90 s (faster for tiny diffs):

| Where | What you should see |
|---|---|
| **Phone** | Info-level ntfy notification: title `Review posted on PR #N`, body shows duration and comment length, click → opens the PR. |
| **Dashboard runs table** | Row transitions from `running` to `completed`, `artifact_url` filled. |
| **GitHub** | `gh pr view <N> --comments` shows a review comment authored by your `gh` identity. |

---

## 8. Verify failure paths

### 8a. Peer agent down → `run.failed`

Stop the A2A bridge in Terminal 1 (`Ctrl-C`). Make a fresh push to the same PR:

```bash
echo "fail-path" >> QUICKSTART.txt
git commit -am "trigger update"
git push
```

Within ~35 s:

- Phone receives an **error**-level notification (high priority, vibrates).
- Dashboard shows a row in `failed` state with a non-empty `error` payload.
- GitHub PR has NO new review comment.

Restart the bridge before continuing.

### 8b. Replayable history across restart

While a run is in progress, kill BOTH the daemon (Terminal 2, `Ctrl-C`) and the dashboard (Terminal 3, `Ctrl-C`).

Restart the dashboard alone:

```bash
uv run orchestrator dash
```

The recent runs table and event tail still render the historical record.

Restart the daemon:

```bash
uv run orchestrator serve
```

The killed-mid-flight run appears as `orphaned` in the runs table within ~1 s of the next dashboard refresh.

### 8c. Dashboard auto-update

With the daemon running, push a third PR. The dashboard runs table and event tail update without you touching anything — refresh latency under 1 s (SC-003).

---

## 9. Run the test suite

```bash
cd services/orchestrator
uv run pytest                      # contract + unit tests
INTEGRATION=1 uv run pytest        # adds the real-end-to-end tests; needs the env vars above
```

Both suites must be green before the v1 release tag.

Also re-run `services/a2a-bridge`'s suite to make sure the orchestrator's path-dependency on the bridge hasn't broken anything:

```bash
cd ../a2a-bridge
uv run pytest
```

---

## 10. Tear down

- Close the test PR (or merge it).
- Delete the test branch on origin: `git push origin --delete quickstart-test`.
- Stop all three terminals (`Ctrl-C`).
- Optionally clear history: `Remove-Item ~/.claude/orchestrator/events.db` (PowerShell) or `rm ~/.claude/orchestrator/events.db` (bash).
- The ntfy topic continues to exist — to "delete" it, just stop using it. (Public ntfy.sh has no per-topic deletion API; topics evaporate with the messages.)

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Daemon exits with `gh auth not OK` | Token expired or scopes insufficient | `gh auth refresh -s repo` |
| Daemon exits with `a2a peer unreachable` | Bridge not running, wrong port, wrong bearer | Restart bridge; verify `A2A_PEER_URL` and `A2A_BEARER_TOKEN` |
| Phone never gets notifications | Topic typo or app not subscribed | Re-test step 1 with `curl`. The ntfy app shows a cloud icon when subscribed. |
| Dashboard rows stuck in `running` after PR is reviewed | Daemon crashed silently between dispatch and completion event | Check daemon log; restart daemon — orphan recovery on next start will fix display state. |
| Polling never fires on a PR | Repo slug wrong or PR closed before first poll | `gh pr list -R $env:ORCHESTRATOR_REPO --state open` and confirm. |
| `events.db locked` | Some other process opened the db non-WAL | The daemon creates WAL on bootstrap; this should not happen. If it does, stop everything, `rm` the db, restart daemon. |

---

## What's NOT in v1 (deliberately)

If your verification reveals you wanted any of these — they belong in v2/v3, not v1:

- A PR-fix agent that addresses review comments and pushes commits.
- An Issue → Plan → PR agent.
- A webhook-based trigger (this is polling-only).
- Multi-repo support per daemon instance (one daemon = one repo).
- Any feature that makes the orchestrator post line-level review annotations or required-changes blocks (v1 posts a single comment via `gh pr review --comment`).
- Any feature that reuses the ntfy topic for two-way input (one-way push only).
- Per-PR git worktree isolation. The `WorktreeManager` and `ORCHESTRATOR_WORKTREE_*` env vars are present in the source tree as dormant scaffolding for `specs/003-worktree-manager/`. v1 leaves `ORCHESTRATOR_WORKTREE_ENABLED=false` (the default). Setting it to `true` requires `ORCHESTRATOR_REPO_PATH` to point at a real local clone of the watched repo — v1's quickstart deliberately does NOT depend on a local clone.
