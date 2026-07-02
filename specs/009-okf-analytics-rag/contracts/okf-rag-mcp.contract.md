# Contract: okf-rag MCP Server

## Registration

`okf-rag` is an opt-in, client-launched stdio MCP server registered through Cabal MCP tooling / `setup/mcp-templates.json`.

It MUST use `default_enabled: false` and MUST NOT be listed as a runnable Local Agent Services daemon unless a future design changes it into a long-running service.

## Required Tools

- `okf_prepare`
- `okf_search`
- `okf_preflight`
- `okf_context_pack`
- `okf_analytics`
- `okf_usage`

## Tool Requirements

- `okf_context_pack` returns the same required JSON shape as `contracts/context-pack.contract.md`.
- `okf_preflight` returns the same required JSON shape as `contracts/preflight.contract.md`.
- `okf_usage` returns recent usage ledger entries with the shape in `contracts/usage-ledger.contract.md`.
- Each tool call writes a usage ledger entry unless the tool is itself reading usage.
- Tool responses include clear stale/missing-index state instead of crashing the client.
- The server is a thin adapter over `cabal.okf` services; retrieval logic is not duplicated in client-specific prompts.
