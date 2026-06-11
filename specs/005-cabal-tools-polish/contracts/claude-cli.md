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

## C2 — Account state for the home-screen panel (no subprocess)

> **Superseded plan**: this contract originally specified shelling out to
> `claude -p "/status"` and regex-parsing the output for email, plan tier,
> active model, and usage percentages. That approach was **rejected during
> implementation**: `claude -p "/status"` sends the literal text as a *prompt*
> and returns model output, not the interactive status panel — there is no
> headless way to obtain plan tier or usage. See the module docstring of
> `cabal/widgets/claude_stats_panel.py`.

**Implemented contract**: read `~/.claude.json` directly — instant, free, reliable.

```python
data = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
oauth = (data or {}).get("oauthAccount") or {}
email = oauth.get("emailAddress")                      # → ClaudeAccountStatus.email
token_present = bool(oauth.get("organizationUuid"))    # → ClaudeAccountStatus.token_present
```

**Our handling** (`read_claude_account_state()` — never raises):

- File missing: `error = "~/.claude.json not found — run \`claude /login\`"`.
- Unparseable JSON: `error = "~/.claude.json could not be parsed"`.
- Plan tier, 5-hour usage, weekly cap, and active model are **not available
  headlessly** — the panel does not attempt to show them.

## C3 — Detect `claude` presence

**Command**: `shutil.which("claude")`.

No subprocess. If it returns `None`, set `ClaudeAccountStatus.error = "claude CLI not installed"` and use the `.claude.json` fallback.

## Security invariants

- We MUST NOT log or render the contents of:
  - `~/.claude.json["oauthAccount"]["accessToken"]` (if present)
  - any field whose key contains `token`, `secret`, `key`, `password` (case-insensitive)
- The panel may render presence: `✓ token present` / `✗ no token`.
- Spec documents (this tree included) must not embed real account details —
  use placeholder values (`user@example.com`) in any example output.

## Out of scope

- `claude mcp list / add / remove` — already covered by `cabal/mcp_ops.py`; reused via `cabal/claude_cli.py` (R16).
- `claude --print --prompt-stdin` long-prompt variant — not needed for v1 (R10 alternative).
- Interactive `claude` invocation with `app.suspend()` — explicitly rejected for the Init flow.
