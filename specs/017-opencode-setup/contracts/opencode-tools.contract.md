# Contract: OpenCode Bridge Tools

The managed tool files live under `global/opencode/tools/` and are copied to OpenCode's tools directory.

Required tools:

- `claude-ask.ts`: invokes `claude -p` in plan/read-only mode.
- `gemini-ask.ts`: invokes `gemini -p` with plan approval mode.
- `antigravity-chat.ts`: invokes `antigravity chat`.

Each tool must:

- export a default OpenCode tool
- declare a prompt argument
- run in the current OpenCode worktree/directory
- return stdout on success and a redacted error summary on failure
