# Quickstart: GitHub Issue Triage (003)

**Prerequisites**: 002-agent-orchestrator is set up and the daemon runs successfully for PR review. All env vars from `specs/002-agent-orchestrator/quickstart.md` are already set.

---

## Additional Setup (Issue Triage only)

Set one additional env var:

```sh
# Windows (persists across sessions)
setx ORCHESTRATOR_ENABLE_ISSUE_TRIAGE true

# Unix
export ORCHESTRATOR_ENABLE_ISSUE_TRIAGE=true
```

That's it. All other config (`ORCHESTRATOR_REPO`, `ORCHESTRATOR_NTFY_TOPIC`, `A2A_PEER_URL`, `A2A_BEARER_TOKEN`) is reused from 002.

---

## Start the Daemon

```sh
cd services/orchestrator
uv run orchestrator serve
```

You should see startup log lines for **both** the PR trigger and the Issue trigger:
```
INFO  GithubPollTrigger started — repo=owner/repo poll_seconds=30
INFO  GithubIssuesPollTrigger started — repo=owner/repo poll_seconds=30
```

---

## Smoke Test

1. Open a test issue on the watched repo:
   ```sh
   gh issue create --repo owner/repo --title "Test triage" --body "This is a test."
   ```
2. Within `ORCHESTRATOR_POLL_SECONDS` (default 30s), your phone should receive an ntfy notification: "Issue #N detected".
3. Within ~90s, the triage comment appears:
   ```sh
   gh issue view <N> --repo owner/repo --comments
   ```
4. A second notification confirms triage complete with category + routing.

---

## Verify Duplicate Suppression

Run the same `gh issue view` after the next poll cycle fires. The daemon log should show:
```
INFO  run.skipped issue_number=N reason=already_triaged
```
No second comment should appear on the issue.

---

## Disable Issue Triage

```sh
# Windows
setx ORCHESTRATOR_ENABLE_ISSUE_TRIAGE false

# Unix
unset ORCHESTRATOR_ENABLE_ISSUE_TRIAGE
```

Restart the daemon. It reverts to PR-review-only mode (002 behaviour).
