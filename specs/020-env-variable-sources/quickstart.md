# Quickstart: Environment Variables — Multi-Source Browser

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-29

How to run, exercise, and verify this feature once implemented — and what to check first when a
source shows nothing.

---

## Run it

```bash
./run web          # POSIX
.\run.cmd web      # Windows
```

That starts the backend under the dev supervisor (restarts on any `setup/src/cabal/**.py` change,
labelled `[backend]` in the console) plus the Vite dev server. Open the workspace, select a
project, and go to **Machine → Environment variables**.

> `run tauri` spawns the backend from the Rust shell instead, so it does not get backend reload.
> Start `run web` first if you want it; the Tauri shell adopts a running backend.

---

## What you should see

With a project selected, the tab strip is built from what was actually detected:

```text
Curated | System | .env.local | appsettings.json | appsettings.Development.json | GitHub | …
└─ existing ─┘   └────────── discovered per project ──────────┘   └─ per provider ─┘
```

Every tab lists **names only**. Values appear one at a time, and only when you click an eye.

---

## Exercise each user story

| Story | How | Expect |
|---|---|---|
| US1 repo files | Select a project with `.env*` / `appsettings*.json` | One tab per file, keys listed, zero values on screen |
| US2 reveal | Click the eye on one row | That row's value only; every other row stays masked |
| US2 auto-mask | Reveal, then switch tab or project | Value returns to masked with no further action |
| US3 GitHub | Select a repo with environments | Tab per environment + repo-level; secrets show a **disabled** eye |
| US4 Azure | Select an Azure-linked project | Key vault + app environment names; the link reason is stated |
| US5 Vercel | Select a Vercel-linked project | Names per target; `sensitive` entries show a disabled eye |
| US6 explicit link | Record an Azure scope, reopen | Recorded scope wins; reason says so |
| US7 .NET | Open a .NET project | Fully-qualified keys (`Logging:LogLevel:Default`); secret store as its own tab |

---

## Verify the guarantees, not just the happy path

**Names-only on load** — the strongest check is at the wire, not the screen:

```bash
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:$PORT/api/env/sources" \
  | python -c "import json,sys; print('value keys found:', json.dumps(json.load(sys.stdin)).count('\"value\"'))"
```

Must print `0`. If it prints anything else, FR-008 is broken regardless of what the UI shows.

**Read-only** — after a full browsing session, check the provider side: GitHub's repo audit log,
Azure Activity Log, and Vercel's project activity must show zero create/update/delete from this
app (SC-006).

**Audit without leakage** — every reveal appears in the audit trail and none of the records
contains a value (FR-016, SC-007). Check via Machine → Diagnostics, or the audit table directly.

**Nothing on disk** — reveal a value, then search the project and the app's data directory for it.
No hit (FR-015).

**One slow source doesn't stall the page** — the listing must return within its cap with the slow
source marked `degraded`, everything else usable (FR-039, SC-010).

---

## When a source shows nothing

The four outcomes are deliberately distinct — read the tab before debugging:

| What you see | Meaning | Do |
|---|---|---|
| No tab at all | `not_linked` — no link signal for this project | Expected; nothing to fix |
| Tab, "nothing configured" | `empty` — reachable, authenticated, holds nothing | Expected; the provider really is empty |
| Tab with a hint | `degraded` — the hint names the cause | Act on the hint |
| Tab with rows | `ok` | — |

Common `degraded` hints and their fixes:

```bash
az account show          # "sign-in required" for Azure
gh auth status           # "sign-in required" for GitHub
echo $VERCEL_TOKEN       # missing credential for Vercel
```

`vercel` is not installed on the development machine this was designed on — that is a supported
state, not a bug. The REST path with `VERCEL_TOKEN` is primary.

**A disabled eye is not a failure.** GitHub secrets and Vercel `sensitive` entries can never be
read back — the platforms do not return them. The row says so; there is nothing to fix.

---

## Agreed copy for the five non-happy states (T010)

Reviewed before any UI was built, because these five are what the module spends most of its
time showing. Each states a fact and, where the reader can act, names the action. None of them
uses the word "error" for a condition that is not one.

| State | Where it renders | Copy | Why this wording |
|---|---|---|---|
| `not_linked` | Nowhere — the tab is absent | *(no copy)* | FR-005: an absent source occupies no space. Explaining every provider a project does *not* use would be the loudest thing on screen. |
| `empty` | In the tab body, in place of the table | **Nothing configured here.** `<Source>` is reachable and signed in — it just holds no variables for this project. | Names the source, states both halves (reachable *and* empty) so it cannot be misread as a failed load. |
| `degraded` | A strip above the table, tab still selectable | **`<Source>` is only partly readable.** `<hint>` | The hint is the whole message; the strip only frames it. FR-034/35/36 require the hint to name the missing tool, the sign-in, or the timeout. |
| `denied` (per row, after a reveal) | In the row's value cell, replacing the eye | **Permission denied.** `<reason naming the access required>` | FR-021: in-row so the rest of the list stays usable, and it names the role rather than saying "try again". |
| `never` (per row, before any reveal) | The eye itself, permanently disabled | Control label: **Value cannot be retrieved** · tooltip: `<reason>` — e.g. "GitHub never returns secret values" | FR-018: a fact, not a failure. The control stays visible so its absence is not read as an oversight, but it never looks retryable. |

Two rules the copy must keep:

- **`empty` and `degraded` never share wording.** "Nothing configured" and "only partly readable"
  are different claims; collapsing them into "no data" is precisely the ambiguity FR-037 exists
  to remove.
- **`denied` and `never` never share wording.** `denied` is about *this* caller and can change;
  `never` is about the platform and cannot. A retry affordance belongs to the first and must not
  appear on the second.

---

## Tests

```bash
# Backend — contract tests first (Constitution Gate 3).
# Note: the webapi suites live in the repo-root tests/ tree, not setup/tests/, which holds
# the TUI and service tests. plan.md named the wrong tree; these are the real paths.
uv run pytest tests/contract/test_env_sources_contract.py -q
uv run pytest tests/unit/test_envsource_discovery.py tests/unit/test_envsource_dotnet.py -q
uv run pytest tests/unit/test_envsource_collectors.py -q      # degradation matrix

# Frontend
cd apps/cabal-desktop && pnpm exec vitest run tests/envSources.test.tsx
```

The degradation matrix is the one to keep green: absent CLI, unauthenticated CLI, missing
credential, timeout, empty provider, malformed file, and unpopulated secret store must each
produce their own state and their own message — never an exception, and never a blank tab.
