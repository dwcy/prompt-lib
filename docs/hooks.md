# Hooks — when they fire and what they do

A hook is a script bound to a Claude Code lifecycle event in `settings.json`. Hooks see structured JSON on stdin, can emit `additionalContext` for Claude, and signal allow/block via exit code (`0` = allow, `2` = block + show reason).

This repo binds five hook scripts across four events.

## SessionStart — `session-start.ps1`

**Fires**: once, when Claude Code launches in a directory.

**What it does**:

```
cwd has CLAUDE.md?
├─ NO  → inject: "Ask the user to describe this project so I can create CLAUDE.md.
│                If they say later, skip and remind next session."
└─ YES → detect stack hints (.NET / Python / frontend / Unity / monorepo) by
         scanning for *.sln, *.csproj, requirements.txt, pyproject.toml,
         Pipfile, package.json, *.unity, etc.
         inject: "Invoke @load-project to brief yourself on this project."
```

**Why this exists**: every new session would otherwise start cold. The hook converts cold-start into a deterministic bootstrap — the model knows whether it's in a fresh project or a familiar one before you type anything.

**Output**: emits a JSON object with `additionalContext` on stdout. Never fails the session.

**Also enforces parallel-session isolation** (see `docs/parallel-isolation.md`): on non-`main` feature branches, claims a per-branch lock at `<git-common-dir>/claude-session-locks/<branch>.json`. If a second session lands on the same branch in the same cwd while the first PID is alive, auto-creates a sibling worktree on a new branch (`<branch>-s2`, `-s3`, …) and tells the user to switch. Opt-out with `CLAUDE_WORKTREE_AUTO=0`.

## PreToolUse (Bash / PowerShell) — `command_guard.py`

**Fires**: before every shell command, on both Bash and PowerShell tools.

**What it inspects**:

- **Hidden Unicode** — zero-width spaces, RTL/LTR override, line/paragraph separators, BOM, soft hyphen. Source files containing these have been used for prompt injection (a command that *looks* harmless but contains an invisible payload).
- **Obfuscated execution** — base64 piped to `bash`/`sh`, `eval` of fetched content, hex-decoded payloads.
- **Destructive patterns** — anything that matches the `deny` list at runtime (force-push, hard-reset, recursive deletes of root/home).

**Exit codes**:

- `0` — allow. The command runs.
- `2` — block. Claude sees a JSON reason and stops; user sees the same message.

**Why both `Bash` and `PowerShell` matchers**: this repo runs on Windows, but Claude Code may also issue Bash via Git Bash. Both shells are guarded so injection doesn't sneak in via the less-watched path.

**Critical implementation note**: the script uses `\u`-escaped Unicode for the dangerous-character table. Editing the script and pasting literal Unicode in place of those escapes can silently corrupt them into ASCII spaces — which causes every command containing a normal space to be flagged as a "paragraph separator." Don't replace the escapes.

## PreToolUse (Write / Edit) — `file_write_guard.py`

**Fires**: before every `Write` or `Edit` tool call.

**What it does**: blocks any attempt to modify the two security-critical files themselves:

```
~/.claude/hooks/command_guard.py
~/.claude/hooks/file_write_guard.py
```

Everything else under `~/.claude/` is freely editable. This is a narrow, deliberate fence — it stops a prompt-injected instruction from disabling the guards as part of its payload.

**Why it's narrow**: a broader "no edits to `~/.claude/`" rule would block your own legitimate config edits. The guard only fences itself and its sibling.

## PreToolUse (Task) — `pretool_task_isolation.py`

**Fires**: before every `Task` (subagent dispatch) tool call.

**What it does**: enforces the parallel-isolation rule documented in `docs/parallel-isolation.md`. Blocks a `Task` call when **all** of these hold:

- `subagent_type` is **not** in the read-only allowlist (`Explore`, `Plan`, `claude-code-guide`, `statusline-setup`, `code-plan-verifier`, `gitignore-auditor`, `github-config-manager`, `load-project`, `secret-auditor`).
- `run_in_background: true`.
- `isolation` is not `"worktree"`.

**Why**: two background writing agents on the same working tree silently overwrite each other (no git conflict, no warning — just a missing diff). The rule existed only in docs; this hook closes the doc-only gap for the most common anti-pattern.

**V1 gap**: two foreground concurrent `Task` calls in one assistant message both see `run_in_background: false` and slip through. Closing that needs cross-invocation state and is deferred.

## PostToolUse (Write / Edit) — `write_audit.py`

**Fires**: after every successful `Write` or `Edit` tool call.

**What it does**: appends one line of JSON to `~/.claude/write_audit.jsonl`:

```json
{"ts": "2026-05-10T14:32:11+00:00", "tool": "Write", "path": "C:/projects/foo/bar.ts"}
```

**Why**: forensic trail. If something gets unexpectedly modified, you can grep this file by timestamp and path. It's append-only, never read by Claude, never affects behaviour.

## Stop — `stop-session.ps1`

**Fires**: when the session ends.

**What it does**: if the cwd is a git repo and `git status --porcelain` shows uncommitted changes, injects:

```
Session ending with N uncommitted change(s) on branch '<branch>'.
Consider committing or stashing before closing.
```

**Why**: you stop forgetting to commit the change you just made. The hook is non-fatal — if anything fails, the session still stops cleanly.

## SessionEnd — `session_end_release_lock.py`

**Fires**: once, when the session terminates (alongside `session_end.py` which prints a farewell).

**What it does**: looks up the per-branch lock file at `<git-common-dir>/claude-session-locks/<branch>.json` (the same path the SessionStart hook writes). If the lock's `cwd` matches the current session's cwd, deletes it.

**Why cwd, not PID**: the SessionEnd hook runs as a subprocess of the same Claude process that claimed the lock, but PIDs can be reused across sessions. cwd is the unique key per session.

**Stale locks**: if the session was killed (no SessionEnd fires), the lock stays on disk. The SessionStart hook's PID-alive check (POSIX `os.kill(pid, 0)`, Windows `tasklist`) treats it as stale and reclaims it on the next start.

## Hook composition with skills

Hooks are unconditional — they fire on every matching event. Skills are voluntary — you invoke them. They layer cleanly:

- `command_guard` (hook) blocks the unsafe shape of a command before it runs.
- `/git commit` (skill) refuses to run on `main` and enforces commit-message conventions.
- `write_audit` (hook) records that the commit's pre-changes happened.

Different layers, different responsibilities. No overlap.

## Adding a hook

1. Drop the script under `global/hooks/<name>.py` (or `.ps1`).
2. Wire it in `global/settings.json` under `hooks.<event>`. Pick a `matcher:` if the event has one (e.g. `Bash`, `Write`).
3. Make sure your script reads JSON from stdin and exits with the right code (`0` allow, `2` block, anything else = error → also allow but logged).
4. `python setup/settings-configurator-ui.py` → restart Claude Code.

**Don't break the boot**: a SessionStart hook that errors out can still let you in, but a hook that hangs will make sessions feel broken. Wrap your script body in `try/except` and exit `0` on unexpected errors unless blocking is the explicit intent.
