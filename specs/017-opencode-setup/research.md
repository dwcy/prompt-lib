# Research: OpenCode Setup

## D1 - OpenCode target directory

**Decision**: Use `~/.config/opencode` for global assets and project `opencode.json` plus `.opencode/` for project assets.

**Rationale**: This matches OpenCode's documented global/project config model and keeps prompt-lib from writing into Claude runtime state.

## D2 - Skill conversion source

**Decision**: Convert from `global/codex/skills` rather than raw Claude skills.

**Rationale**: Codex-compatible skills already replace Claude-specific session assumptions with cross-tool `AGENTS.md` guidance and `SKILL.md` frontmatter.

## D3 - JSON apply behavior

**Decision**: Merge JSON config files recursively and copy non-JSON assets.

**Rationale**: OpenCode users may already have provider/model settings; Cabal should add prompt-lib integration without deleting unrelated keys.

## D4 - Codex bridge

**Decision**: Register Codex as a local OpenCode MCP server using `codex mcp-server`.

**Rationale**: The installed Codex CLI exposes a stdio MCP server mode, so it can be integrated as a tool surface instead of only as a shell command.

## D5 - Claude, Gemini, and Antigravity bridges

**Decision**: Expose Claude and Gemini through non-interactive CLI command tools and Antigravity through its `chat` command.

**Rationale**: Claude and Gemini expose print/prompt modes; Antigravity exposes chat launch and MCP consumer registration but not a stdio MCP server.

## D6 - OpenCode CLI vs desktop install targets

**Decision**: Treat OpenCode Terminal/CLI and OpenCode Desktop as separate install and status targets. Use npm `opencode-ai` for the CLI, Homebrew cask `opencode-desktop` on macOS, and official `opencode.ai/download/stable/*` desktop endpoints for Windows/Linux desktop installers.

**Rationale**: The official OpenCode download page separates OpenCode Terminal from OpenCode Desktop (Beta). Cabal should not label the npm CLI package as if it installed both products.
