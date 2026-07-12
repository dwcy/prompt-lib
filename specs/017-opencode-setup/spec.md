# Feature Specification: OpenCode Setup

**Feature Branch**: `feat/opencode-setup`
**Created**: 2026-07-12
**Status**: Implemented

## User Scenarios & Testing

### User Story 1 - See and install OpenCode CLI/Desktop (P1)

A maintainer opens Cabal and can see whether the OpenCode CLI and desktop app are installed, then launch the appropriate installer when either is missing.

**Independent Test**: Open the OpenCode Setup screen; status chips show CLI/desktop/config/bridge availability and each install button appears only when that target is absent.

### User Story 2 - Deploy prompt-lib assets to OpenCode (P1)

A maintainer can convert prompt-lib's global/Codex-compatible assets into OpenCode locations, preview what changes, and apply global or project-local setup.

**Independent Test**: Preview lists config, tools, compatible skills, and references; applying copies or merges selected assets into the target.

### User Story 3 - Bridge other agent CLIs from OpenCode (P2)

A maintainer can expose Codex as an OpenCode MCP server and expose Claude, Gemini, and Antigravity as opt-in command tools where those CLIs support a callable mode.

**Independent Test**: Generated OpenCode config contains the Codex MCP entry and generated tools contain Claude, Gemini, and Antigravity wrappers with ask permissions.

## Functional Requirements

- **FR-001**: Cabal MUST show an OpenCode Setup entry on Home.
- **FR-002**: The OpenCode screen MUST report OpenCode CLI, OpenCode desktop app, OpenCode config, skills, tools, Codex CLI, Codex MCP, Claude CLI, Gemini CLI, and Antigravity availability.
- **FR-003**: If the OpenCode CLI or desktop app is missing, the screen MUST expose target-specific installer actions: npm `opencode-ai` for CLI, and official OpenCode Desktop download/cask paths for the desktop app.
- **FR-004**: The screen MUST preview global and project OpenCode assets before applying them.
- **FR-005**: Applying global setup MUST write to `~/.config/opencode` without replacing unrelated existing JSON keys.
- **FR-006**: Applying project setup MUST write project `opencode.json` and `.opencode/` assets.
- **FR-007**: Converted skills MUST come from existing Codex-compatible skill assets under `global/codex/skills`.
- **FR-008**: Claude-only runtime features such as hooks and statusline MUST NOT be activated as OpenCode runtime behavior.
- **FR-009**: Generated Codex MCP config MUST be opt-in/ask-gated.
- **FR-010**: Claude, Gemini, and Antigravity bridge tools MUST be opt-in/ask-gated.

## Success Criteria

- **SC-001**: A maintainer can reach OpenCode setup from Cabal Home in one action.
- **SC-002**: A missing OpenCode CLI is clearly distinguished from a missing OpenCode desktop app and missing config/assets.
- **SC-003**: A first apply creates valid JSON config and at least one compatible skill/tool asset.
- **SC-004**: Existing unrelated OpenCode JSON settings survive apply.
- **SC-005**: Focused helper and screen tests pass.

## Assumptions

- OpenCode global config lives under `~/.config/opencode`.
- OpenCode can consume Agent Skills in `SKILL.md` format, so existing Codex-compatible skill assets are the safest conversion source.
- OpenCode Terminal and OpenCode Desktop are separate install targets; npm `opencode-ai` installs the CLI only.
- Antigravity currently exposes chat launch and MCP consumer registration, not a stdio MCP server.
