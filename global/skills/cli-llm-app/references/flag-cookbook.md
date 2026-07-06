# CLI flag cookbook — claude & codex

Every entry here was verified empirically. The ones marked **gotcha** silently misbehave with no error — they're the ones that cost the most time.

## Claude Code (`claude`)

### Core flags for an app backend

| Flag | Why |
|---|---|
| `--print` | Non-interactive. Required for any non-TTY use. |
| `--model <full-id>` | Pin the model. See below — aliases are unreliable. |
| `--permission-mode plan` | Skip permission prompts. The app should never let the model write/exec. |
| `--no-session-persistence` | Don't write the conversation to `~/.claude/projects/*`. Session history still works *within* a live process — this only controls disk persistence. |

### Startup-overhead trim (preserves OAuth)

| Flag | Why |
|---|---|
| `--strict-mcp-config` | Don't auto-load MCP servers. Saves ~2–3s. |
| `--disable-slash-commands` | Skip skill discovery. Saves ~1s. |
| `--tools ""` | Don't register tools. Saves ~0.5–1s. |

Net effect: roughly 5s shaved off a ~12s cold start, down to ~7s. Auth still works because OAuth/keychain reads are not stripped.

### Persistent-session flags

| Flag | Why |
|---|---|
| `--input-format stream-json` | Read NDJSON events from stdin. |
| `--output-format stream-json` | Emit NDJSON events to stdout. |
| `--verbose` | **Mandatory** when combining `--print` with `--output-format stream-json`. Error message: `When using --print, --output-format=stream-json requires --verbose`. |
| `--system-prompt <text>` | Set the system prompt once at spawn. Conversation history is then server-side; per-turn prompts are just the user message. |
| `--include-partial-messages` | Optional. Streams `assistant` chunks as they're generated. For block-on-result hosts: leave off. |

### Gotchas

- **`--model haiku` is silently ignored** (alias falls back to default Sonnet). Use the full ID `claude-haiku-4-5`. Verify by sending `"what model are you?"` on a fresh session and reading the reply or the `system/init` event's `model` field.
- **`--bare` breaks OAuth.** It strips hooks, plugin sync, auto-memory, CLAUDE.md, keychain reads. Auth becomes strictly `ANTHROPIC_API_KEY` env var or `apiKeyHelper` via `--settings`. If the user is on subscription/OAuth, `--bare` returns `Not logged in · Please run /login`.
- **`subprocess.run(["claude", ...])` on Windows throws `FileNotFoundError`.** npm-global CLIs are installed as `.cmd` shims that aren't auto-resolved by Python's subprocess module. Use `shutil.which("claude")` (or your language equivalent) and pass the absolute path.

### Model IDs (current, full form)

| Tier | Full ID |
|---|---|
| Fastest | `claude-haiku-4-5` |
| Balanced | `claude-sonnet-4-6` |
| Smartest | `claude-opus-4-7` |

Aliases (`sonnet`, `opus`) seem to work in the CLI's own help text but have produced surprises. Always use the full ID for app code.

## Codex (`codex`)

### Core flags for one-shot fallback

| Flag | Why |
|---|---|
| `codex exec` | Non-interactive subcommand. |
| `--skip-git-repo-check` | Don't refuse to run outside a git repo. |
| `--sandbox read-only` | Block writes. App is the orchestrator; the model shouldn't touch the filesystem. |
| `--ephemeral` | Don't persist the session. |
| `-` | Read the prompt from stdin (cleaner than passing huge prompts as argv). |
| `-m <model>` | Override the model. |

### Auth-tier gotcha

Codex authenticates either via ChatGPT subscription account or an OpenAI API key. **The auth mode controls which models you can pass to `-m`.**

| Auth | Models that work |
|---|---|
| ChatGPT account | Default only — currently `gpt-5`. `gpt-5-mini`, other API-tier models → `"The 'X' model is not supported when using Codex with a ChatGPT account."` |
| API key | All API-listed models, including `gpt-5-mini` |

Switching auth: `codex logout`, then `codex login` and pick the API-key flow. Billed against the OpenAI API account, not the ChatGPT subscription.

### No persistent mode

Codex's `exec` is one-shot. There's no equivalent to claude's `--input-format stream-json` that keeps a chat session alive over stdin/stdout. So in a hybrid app:

- Claude = primary persistent session.
- Codex = stateless one-shot fallback only.

### Windows path resolution

Same `.cmd` shim issue as claude. Resolve via `shutil.which("codex")` and use the absolute path.

## Verification snippets

### Confirm claude actually selected the requested model

```bash
echo "what model are you? answer with only the exact model id, nothing else." \
  | claude --print --model claude-haiku-4-5 --permission-mode plan --no-session-persistence --output-format text
```

Should print `claude-haiku-4-5`. If it prints `claude-sonnet-4-6`, the alias resolution silently failed — fix the flag.

### Confirm codex auth tier

```bash
codex auth status   # tells you ChatGPT vs API key
```

Or just probe a restricted model:

```bash
echo "hi" | codex exec --skip-git-repo-check --sandbox read-only --ephemeral -m gpt-5-mini -
```

If you get `"not supported when using Codex with a ChatGPT account"`, you're on subscription auth.
