# Context Guard — advisory /compact nudge

Opt-in, off by default. Two cooperating pieces read the same policy file and never anything more:

- `global/hooks/context_guard.py` — a `UserPromptSubmit` hook.
- The `context_guard` segment in `global/statusline.py`.

Both read `~/.claude/context-guard-policy.json` (deployed from `global/context-guard-policy.json`, seeded once — never overwritten on redeploy):

```json
{
  "enabled": false,
  "threshold_percent": 80,
  "max_context_tokens": 200000
}
```

Toggle it from the cabal TUI: Home → Claude Settings → **Context Guard**. That screen (`setup/src/cabal/views/context_guard.py`) reads/writes the same file via `setup/src/cabal/context_guard_policy.py`.

## What this is not

**This cannot trigger or force compaction.** No Claude Code hook has a mechanism to cause a compaction — `PreCompact` can only `block` a compaction Claude Code's own logic already decided to run. Context Guard is advisory only: it estimates usage and *asks* the agent (via `hookSpecificOutput.additionalContext` on `UserPromptSubmit`) to consider running `/compact` soon. The agent may act on it or ignore it.

**No hook receives a real context-window/token-usage field.** Documented hook input is limited to `session_id`, `prompt_id`, `transcript_path`, `cwd`, `permission_mode`, `effort`, `hook_event_name` (+ subagent/model fields on some events). There is no `max_context_tokens` Claude Code itself can report, since it varies by model (e.g. 200k vs. a 1M-context model) — hence the setting is yours to configure, not auto-detected.

## How usage is estimated

Both pieces read the session's transcript JSONL (`transcript_path`) and scan backward from the end for the most recent `type: "assistant"` entry's `message.usage` object, summing:

```
input_tokens + cache_creation_input_tokens + cache_read_input_tokens + output_tokens
```

This was verified empirically against real transcript files (each Claude API response embeds this `usage` object on the assistant entry) rather than assumed from third-party docs. The scan is tail-bounded (expanding read window, capped at 8 MB) so one very long session doesn't slow down every prompt submission.

The statusline segment duplicates this same estimator rather than importing it, because `global/statusline.py` and `global/hooks/context_guard.py` are deployed to different directories and run as independent standalone processes — this repo's existing hooks already duplicate small helpers (e.g. `_git_executable()`) across scripts for the same reason.

## Editing the policy

- Cabal TUI: Home → Claude Settings → Context Guard.
- By hand: edit `~/.claude/context-guard-policy.json` directly, restart Claude Code.

`threshold_percent` must be an integer 1–100; `max_context_tokens` must be a positive integer. Absence of the file (or `enabled: false`) means the feature is fully off — neither the hook nor the statusline segment does any work.
