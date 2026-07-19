# Hooks — when they fire and what they do

A hook is a script bound to a Claude Code lifecycle event in `global/settings.json`. Hooks see structured JSON on stdin, can emit `additionalContext` for Claude, and signal allow/block via exit code (`0` = allow, `2` = block + show reason).

This repo binds 14 hook scripts across 7 lifecycle events: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, `SessionEnd`. All are Python (`global/hooks/*.py`) except the Windows-only sibling script `claude-process-check.ps1`, which `process_cleanup.py` shells out to. Every hook honors `PROMPTLIB_DISABLED_HOOKS=<name>` (and `PROMPTLIB_HOOK_PROFILE=off`) via the shared `_gate.should_skip()` helper, and every hook fails open — an unexpected error exits `0` (allow) rather than breaking the session.

## SessionStart — `session_start.py` + `process_cleanup.py`

**Fires**: once, when Claude Code launches in a directory. Both hooks run.

### `session_start.py`

**What it does** (in order):

```
1. Auto-name the session "<dir> · <branch>" for /resume and the terminal title.
2. Parallel-session collision check (see docs/parallel-isolation.md):
   on a non-main/master branch, claim a per-branch lock at
   <git-common-dir>/claude-session-locks/<branch>.json.
   If another live session already holds it (PID-alive check — POSIX
   os.kill(pid, 0), Windows tasklist) and it's not the same cwd:
     CLAUDE_WORKTREE_AUTO=0 → emit instructions to create a worktree manually.
     otherwise → run `git worktree add ../<repo>-<branch>-sN -b <branch>-sN`
                 from the main checkout, tell Claude to refuse writes in the
                 current cwd until the user switches.
   Collision handling short-circuits the rest of the hook — no stack
   detection runs this pass.
3. cwd has no CLAUDE.md?
   ├─ looks like an existing codebase (manifest/source files present)
   │    → inject: "ask the user to describe this project so a CLAUDE.md can
   │      be created; if they decline, proceed without it."
   └─ looks empty/new
        → inject: "proactively invoke @init-project rather than
          hand-creating files."
4. cwd has CLAUDE.md → detect stack hints (.NET / Python / JS-TS / Monorepo /
   Unity3D) by scanning for *.sln, *.csproj, requirements.txt, pyproject.toml,
   Pipfile, package.json (+ workspace markers), Assets/ProjectSettings, etc.
   → inject: "invoke @load-project to brief yourself on this project."
```

**Why this exists**: every new session would otherwise start cold. The hook converts cold-start into a deterministic bootstrap — the model knows whether it's in a fresh project, a familiar one, or a branch another session already owns, before you type anything.

**Output**: emits a JSON object with `additionalContext` (and a `sessionTitle`) on stdout. Never fails the session.

### `process_cleanup.py` (also runs on `SessionEnd` — see below)

## UserPromptSubmit — `context_guard.py`

**Fires**: before every user prompt is processed.

**What it does**: advisory-only context-window nudge, **off by default** (opt-in via `~/.claude/context-guard-policy.json`, `enabled: true`). When on, it tails the session transcript for the most recent assistant message's token `usage` (`input` + `cache_creation` + `cache_read` + `output`), and if that estimate crosses `threshold_percent` of the configured `max_context_tokens`, injects a suggestion to consider `/compact`.

**Why this exists**: no Claude Code hook can trigger or force compaction — only `PreCompact` can block a compaction Claude Code already decided to run. This hook can only ask.

See [`context-guard.md`](context-guard.md) for the full field derivation and policy schema.

## PreToolUse (Bash / PowerShell) — `command_guard.py`

**Fires**: before every shell command, on both `Bash` and `PowerShell` tools.

**What it inspects**:

- **Hidden Unicode** — zero-width spaces, RTL/LTR override, line/paragraph separators, BOM, soft hyphen. Source files containing these have been used for prompt injection (a command that *looks* harmless but contains an invisible payload).
- **Obfuscated execution** — base64 piped to `bash`/`sh`, `eval` of fetched content, hex-decoded payloads.
- **Destructive patterns** — anything that matches the `deny` list at runtime (force-push, hard-reset, recursive deletes of root/home).

**Exit codes**:

- `0` — allow. The command runs.
- `2` — block. Claude sees a JSON reason and stops; user sees the same message.

**Why both `Bash` and `PowerShell` matchers**: this repo runs on Windows, but Claude Code may also issue Bash via Git Bash. Both shells are guarded so injection doesn't sneak in via the less-watched path.

**Critical implementation note**: the script uses `\u`-escaped Unicode for the dangerous-character table. Editing the script and pasting literal Unicode in place of those escapes can silently corrupt them into ASCII spaces — which causes every command containing a normal space to be flagged as a "paragraph separator." Don't replace the escapes.

## PreToolUse (Write / Edit) — `file_write_guard.py` + `pretool_branch_guard.py`

**Fires**: before every `Write` or `Edit` tool call. Both hooks run.

### `file_write_guard.py`

**What it does**: blocks any attempt to modify the two security-critical files themselves:

```
~/.claude/hooks/command_guard.py
~/.claude/hooks/file_write_guard.py
```

Everything else under `~/.claude/` is freely editable. This is a narrow, deliberate fence — it stops a prompt-injected instruction from disabling the guards as part of its payload.

**Why it's narrow**: a broader "no edits to `~/.claude/`" rule would block your own legitimate config edits. The guard only fences itself and its sibling.

### `pretool_branch_guard.py`

**What it does**: enforces "branch before starting work" (see `global/CLAUDE.md`). Resolves the git repo containing the file being written/edited; if its current branch is in `~/.claude/git-policy.json`'s `refuse_on_branches` list (default `["main", "master"]`), blocks the edit with instructions to `git checkout -b <type>/<slug>` first.

**Fail-open**: no repo, git missing, unreadable policy, or detached HEAD → allow. **Bypass**: `PROMPTLIB_DISABLED_HOOKS=pretool_branch_guard`.

**Why this exists**: branching used to be a documentation-only convention ("branch before the first edit"). This hook makes it impossible to silently skip — the block fires at the moment of the first edit, not at commit time when it's too late to avoid mixing unrelated work into `main`.

## PreToolUse (Task | Agent) — `pretool_task_isolation.py` + `subagent_start.py`

**Fires**: before every subagent dispatch (`Task` in older Claude Code, `Agent` in current — both matched). Both hooks run.

### `pretool_task_isolation.py`

**What it does**: enforces the parallel-isolation rule documented in `docs/parallel-isolation.md`. Blocks a dispatch when **all** of these hold:

- `subagent_type` is **not** in the read-only allowlist (`Explore`, `Plan`, `claude-code-guide`, `statusline-setup`, `code-plan-verifier`, `gitignore-auditor`, `github-config-manager`, `load-project`, `secret-auditor`).
- `run_in_background: true`.
- `isolation` is not `"worktree"`.

**Why**: two background writing agents on the same working tree silently overwrite each other (no git conflict, no warning — just a missing diff). The rule existed only in docs; this hook closes the doc-only gap for the most common anti-pattern.

**V1 gap**: two foreground concurrent dispatches in one assistant message both see `run_in_background: false` and slip through. Closing that needs cross-invocation state and is deferred.

### `subagent_start.py`

**What it does**: records `{name, model, started_at, session_id}` to `~/.claude/.subagent_state.json` and prints a one-line `▶ subagent running: <name>` chat notice, so the statusline can show an active-subagent chip. Mirrors the same read-only allowlist as `pretool_task_isolation.py` (kept in sync by comment convention) and skips recording when the dispatch is about to be blocked by that hook — otherwise the chip would be left stale with no `SubagentStop` event to clear it. Cleared by `subagent_stop.py`.

**Why hook `PreToolUse(Task|Agent)` and not `SubagentStart`**: the dispatched model is only available here (`tool_input.model`); the `SubagentStart` event payload has no model field.

## PostToolUse (all tools) — `post_tool_use.py`

**Fires**: after every tool call, any tool.

**What it does**: increments `{session_id, agent_count, tool_count}` in `~/.claude/.session_state.json` (resetting when `session_id` changes). The statusline reads this file to render an activity-counter segment.

## PostToolUse (Write / Edit) — `write_audit.py` + `format_on_write.py`

**Fires**: after every successful `Write` or `Edit` tool call. Both hooks run.

### `write_audit.py`

**What it does**: appends one line of JSON to `~/.claude/write_audit.jsonl`:

```json
{"ts": "2026-05-10T14:32:11+00:00", "tool": "Write", "path": "C:/projects/foo/bar.ts"}
```

**Why**: forensic trail. If something gets unexpectedly modified, you can grep this file by timestamp and path. It's append-only, never read by Claude, never affects behaviour.

### `format_on_write.py`

**What it does**: auto-formats the just-written file by extension — `.py` → `ruff format` (only if a `pyproject.toml`/`ruff.toml`/`.ruff.toml` is found upwards from the file, and only if the file still parses as valid Python after formatting, else the pre-format bytes are restored), `.ts`/`.tsx`/`.js`/`.jsx`/`.json`/`.jsonc` (+ `.mts`/`.cts`/`.mjs`/`.cjs`) → `biome format --write` (only if a `biome.json`/`biome.jsonc` is found), `.cs` → `dotnet format --include <file>` (only if a `.sln`/`.csproj` is found). Silently skips vendored/build directories (`node_modules`, `.git`, `venv`, `bin`, `obj`, `dist`, `build`, `.next`, `.nuxt`, `target`, etc.), missing tools, missing config, or files over 2 MB.

**Why the parse-check round-trip on Python**: some `ruff format` versions have emitted invalid syntax on certain constructs (e.g. stripping parens from `except (A, B):`). The hook snapshots the file, checks it parsed *before* formatting, and reverts to the snapshot if formatting broke a previously-valid file — a buggy formatter must never corrupt working code.

## Stop — `stop_session.py`

**Fires**: when the session ends.

**What it does**: if the cwd is a git repo and `git status --porcelain` shows uncommitted changes, injects:

```
Session ending with N uncommitted change(s) on branch '<branch>'.
Consider committing or stashing before closing.
```

**Why**: you stop forgetting to commit the change you just made. The hook is non-fatal — if anything fails, the session still stops cleanly.

## SubagentStop — `subagent_stop.py`

**Fires**: when a dispatched subagent finishes.

**What it does**: reads `~/.claude/.subagent_state.json` (written by `subagent_start.py`) for the subagent's name, deletes the state file, and prints `✓ subagent done: <name> · N,NNN tokens generated` — the token count is measured by summing `output_tokens` across the subagent's own transcript, not estimated.

**Why cost isn't shown**: USD cost isn't exposed to hooks (only the statusLine gets a session-total cost figure), and hand-maintaining a per-model rate table would drift out of date. Token count is a hard number pulled from the transcript; cost is not.

## SessionEnd — `session_end_release_lock.py` + `process_cleanup.py`

**Fires**: once, when the session terminates. Both hooks run.

### `session_end_release_lock.py`

**What it does**: looks up the per-branch lock file at `<git-common-dir>/claude-session-locks/<branch>.json` (the same path `session_start.py` writes). If the lock's `cwd` matches the current session's cwd, deletes it.

**Why cwd, not PID**: the `SessionEnd` hook runs as a subprocess of the same Claude process that claimed the lock, but PIDs can be reused across sessions. cwd is the unique key per session.

**Stale locks**: if the session was killed (no `SessionEnd` fires), the lock stays on disk. `session_start.py`'s PID-alive check treats it as stale and reclaims it on the next start.

### `process_cleanup.py`

**Fires**: once at session start, once at session end (both wired in `settings.json`).

**What it does**: on Windows only, shells out to the sibling `claude-process-check.ps1` (the report/kill engine, versioned alongside it) with `-Kill`. That script targets only orphaned Claude-related helpers — `node.exe`, `claude.exe`, `sh.exe`, `bash.exe`, and small unix helpers (`du.exe`, `grep.exe`, `rg.exe`, `tail.exe`, `head.exe`, `uname.exe`, `cygpath.exe`) — whose parent process is gone, and explicitly never flags a `node.exe` that doesn't look Claude-related (protects real dev servers). Appends one line per run to `~/.claude/process_cleanup.log` (`event`, `orphans_found`, `orphans_killed`). Only speaks up via `additionalContext` when something was actually killed, and only on `SessionStart` — `SessionEnd` output is never read by anything.

**Why session boundaries, not mid-session**: Claude Code hooks are lifecycle-driven — there's no "CPU/RAM crossed a threshold" event. A hook can't watch a single long session slowly turning into syrup; it can only sweep what's left behind when a session starts or ends. Catching true mid-session buildup would need an OS-level timer (e.g. Windows Task Scheduler) running independently of Claude Code — deliberately out of scope here. See [ADR 0002](adr/0002-process-cleanup-hook-session-boundaries-not-scheduled-task.md) for the full tradeoff.

**Non-Windows**: no-op. `claude-process-check.ps1` is Windows-only (uses `Get-CimInstance Win32_Process`).

**Never fails the session**: any error exits 0, same convention as every other hook here.

## Not a lifecycle hook: `check_claude_update.py`

Lives in `global/hooks/` alongside the real hooks but is **not** wired to any event in `settings.json` — it's invoked directly by `global/statusline.py` to check for CLI updates, not by the hook dispatcher. Don't look for it in `settings.json`.

## Not a hook: `_gate.py`

Shared helper module (`should_skip(name)`) imported by every hook above for the `PROMPTLIB_DISABLED_HOOKS` / `PROMPTLIB_HOOK_PROFILE=off` bypass. It has no `PreToolUse`/etc. entry point of its own.

## Hook composition with skills

Hooks are unconditional — they fire on every matching event. Skills are voluntary — you invoke them. They layer cleanly:

- `command_guard` (hook) blocks the unsafe shape of a command before it runs.
- `/git commit` (skill) refuses to run on `main` and enforces commit-message conventions.
- `write_audit` (hook) records that the commit's pre-changes happened.

Different layers, different responsibilities. No overlap.

## Adding a hook

1. Drop the script under `global/hooks/<name>.py` (or `.ps1`).
2. Wire it in `global/settings.json` under `hooks.<event>`. Pick a `matcher:` if the event has one (e.g. `Bash`, `Write`, `Task|Agent`).
3. Make sure your script reads JSON from stdin and exits with the right code (`0` allow, `2` block, anything else = error → also allow but logged).
4. Import `_gate.should_skip("<name>")` at the top so `PROMPTLIB_DISABLED_HOOKS` can bypass it.
5. `python setup/settings-configurator-ui.py` → restart Claude Code.

**Don't break the boot**: a SessionStart hook that errors out can still let you in, but a hook that hangs will make sessions feel broken. Wrap your script body in `try/except` and exit `0` on unexpected errors unless blocking is the explicit intent.
