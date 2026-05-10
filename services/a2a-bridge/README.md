# a2a-bridge

A v1 multi-agent A2A bridge: Claude Code delegates tasks to a peer Gemini CLI over the official A2A v1.0.0 JSON-RPC binding, with two adapters (Claude inbound, Gemini outbound target) sharing one Python package.

This package is spec-driven. The authoritative documents live in [`specs/001-a2a-bridge/`](../../specs/001-a2a-bridge/):

- **What it does and why**: [spec.md](../../specs/001-a2a-bridge/spec.md)
- **How to run it (10-minute walkthrough)**: [quickstart.md](../../specs/001-a2a-bridge/quickstart.md)
- **Stack, structure, constitution gates**: [plan.md](../../specs/001-a2a-bridge/plan.md)
- **Wire-format contracts**: [contracts/](../../specs/001-a2a-bridge/contracts/)
- **Phase-by-phase task breakdown**: [tasks.md](../../specs/001-a2a-bridge/tasks.md)

If you are implementing or reviewing this package, read `plan.md` first, then `tasks.md`. Every implementation task lists its file paths and its owning subagent.
