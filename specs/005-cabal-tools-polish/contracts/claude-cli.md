# Contract — `claude` CLI invocation shapes (Part B)

This file documents every external `claude` call. The Claude Code CLI itself is the authoritative spec — this file captures the subset we depend on, and how we handle failure.

Min version: any recent `claude` CLI that supports `-p` / `--print` for non-interactive single-turn prompting.

## C1 — Invoke Claude against the newly-initialised project

**Command** (argv form):

```python
[
    "claude",
    "-p",
    PROMPT,  # contents of <project>/.claude/INIT_PROMPT.md
]
```

**Working directory**: `<ProjectInitPlan.target_dir>` (the freshly-created project).
**Stdin**: `subprocess.DEVNULL`.
**Environment**: `{**os.environ, "MSYS_NO_PATHCONV": "1"}` (R-7 — same shim as `cabal/mcp_ops._run_claude_cli`).
**Process control**: `subprocess.Popen(..., text=True, stdout=PIPE, stderr=PIPE)` so we can stream stdout into the wizard status pane and call `proc.terminate()` from a Cancel button (R10).

**Expected behaviour**:

- Claude reads the prompt, sees `.claude/CLAUDE.md` + `.claude/agents/*.md` + `.claude/skills/*.md` in the cwd, and produces a setup plan (or makes edits — depending on what's in the user's global hooks and skills).
- `claude` exits 0 on success.

**Our handling**:

- Exit 0: status `[green]✓ claude finished[/green]` + the last 200 lines of stdout shown in a `RichLog`.
- Exit ≠ 0 AND ≠ 124 (timeout): status `[yellow]claude exited <N> — review .claude/ manually[/yellow]`. Files are NOT deleted (NFR-8).
- `FileNotFoundError` (`claude` not on PATH): skip this step entirely. Status `[yellow]claude CLI not installed — skipping architecture step. Install from Tools screen.[/yellow]` (FR-15).
- User cancel: `proc.terminate()`, wait 3 s, then `proc.kill()`. Status `[yellow]cancelled[/yellow]`.

## C2 — Fetch account status for the home-screen panel

**Command**:

```bash
claude -p "/status"
```

**Working directory**: `Path.cwd()` (any — the slash-command is account-scoped, not project-scoped).
**Stdin**: `DEVNULL`. **Stdout**: free-form text matching the current `/status` template.
**Timeout**: 15 s. Exit code 124 → "stats unavailable — try again".

**Output shape** (observed, version-dependent — parse defensively per R18):

```
Claude Code v1.2.3
Account: pawzor@gmail.com (Max 20x)
Active model: claude-opus-4-7
5-hour message usage: 42% (211 / 500)
Weekly cap: 18% (1,807 / 10,000)
Session: signed in
```

**Our parsing** (regex per line, all optional — if a line doesn't match, we leave the field as `None`):

| Field | Regex |
|---|---|
| `email` | `^Account:\s+(?P<email>\S+@\S+)` |
| `account_type` | `\((?P<plan>Pro\|Max 5x\|Max 20x\|Team\|Enterprise\|API)\)` |
| `active_model` | `^Active model:\s+(?P<model>\S+)` |
| `five_hour_used_pct` | `^5-hour message usage:\s+(?P<pct>\d+)%` |
| `weekly_cap_used_pct` | `^Weekly cap:\s+(?P<pct>\d+)%` |

**Fallback** (R18): if every regex fails, store the entire stdout in `ClaudeAccountStatus.raw_status_output` and render it verbatim in the panel with a `[dim]could not parse — raw /status below[/dim]` hint.

**No-claude fallback**: read `~/.claude.json`:

```python
data = json.loads((Path.home() / ".claude.json").read_text())
email = (data.get("oauthAccount") or {}).get("emailAddress")
token_present = bool((data.get("oauthAccount") or {}).get("organizationUuid"))
```

`account_type` is unrecoverable from the JSON file alone — leave it `"unknown"`.

## C3 — Detect `claude` presence

**Command**: `shutil.which("claude")`.

No subprocess. If it returns `None`, set `ClaudeAccountStatus.error = "claude CLI not installed"` and use the `.claude.json` fallback.

## Security invariants

- We MUST NOT log or render the contents of:
  - `~/.claude.json["oauthAccount"]["accessToken"]` (if present)
  - any field whose key contains `token`, `secret`, `key`, `password` (case-insensitive)
- The panel may render presence: `✓ token present` / `✗ no token`.
- The full `/status` output may be rendered verbatim IF parsing fails — operator is implicitly trusting `claude` not to print their secrets, which is a reasonable assumption because the official `/status` command is designed for the user to see.

## Out of scope

- `claude mcp list / add / remove` — already covered by `cabal/mcp_ops.py`; reused via `cabal/claude_cli.py` (R16).
- `claude --print --prompt-stdin` long-prompt variant — not needed for v1 (R10 alternative).
- Interactive `claude` invocation with `app.suspend()` — explicitly rejected for the Init flow.
