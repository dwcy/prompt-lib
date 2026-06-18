# AGENTS.md Template

Use this as a generic Codex project instruction file when no stack-specific
template is a better fit.

## Project

Describe what this project is, how it is built, and which files are the source
of truth.

## Commands

- Install:
- Test:
- Lint:
- Build:

## Conventions

- Keep changes focused and compatible with the existing project shape.
- Prefer existing helpers and framework patterns before adding new abstractions.
- Run the smallest useful verification command after changes.

## Codex Skills

Project-local skills live in `.agents/skills/`. Use Cabal's Local Codex Config
panel to sync selected prompt-lib Codex skills into that folder.
