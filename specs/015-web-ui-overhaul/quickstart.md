# Quickstart: Cabal Web UI Overhaul

## Prerequisites

- Python ≥3.11 with `uv` (backend runs from `setup/`)
- Node LTS with **pnpm** (frontend; never npm/yarn)
- Rust stable + Tauri v2 CLI (desktop shell only — not needed for browser-mode dev)
- Windows: MSVC Build Tools (Tauri); POSIX: webkit2gtk per Tauri docs

## Development (browser mode — fastest inner loop)

```bash
# 1. Backend (writes the handshake file with its ephemeral port + token)
cd setup
uv run python -m cabal.webapi --project ..

# 2. Frontend dev server (Vite proxy reads the handshake file for port/token)
cd apps/cabal-desktop
pnpm install
pnpm dev
```

Open the printed Vite URL. Behavior is contract-identical to the desktop shell.

Vite hot-reloads frontend edits. Restart the backend process after Python changes; the development
proxy follows the authenticated handshake dynamically when the backend chooses a new port or token.
Launching through `python -m cabal.webapi` is required because that entrypoint writes the handshake.

## Development (desktop shell)

```bash
cd apps/cabal-desktop
pnpm tauri dev   # spawns/adopts the backend per desktop-shell.contract.md
```

## Tests

```bash
# Backend: contract first, then unit/integration
cd setup && uv run pytest ../tests/contract -k webapi
cd setup && uv run pytest ../tests/unit ../tests/integration -k webapi

# Frontend
cd apps/cabal-desktop && pnpm test        # Vitest + RTL + MSW
cd apps/cabal-desktop && pnpm test:e2e    # Playwright smoke (fixture backend)

# Existing TUI suite MUST stay green (FR-015 / SC-008)
cd setup && uv run pytest ../tests
```

## Production build

```bash
# 1. Sidecar binary
uv run --with pyinstaller python setup/build/build_backend.py

# 2. Desktop bundle (picks up externalBin per tauri.conf.json)
cd apps/cabal-desktop && pnpm tauri build
```

Output: platform installer under `apps/cabal-desktop/src-tauri/target/release/bundle/`.

The Tauri bundle reads the sidecar from `setup/build/dist/cabal-backend-<target-triple>[.exe]`
through `bundle.externalBin`, and the shell launches it as `cabal-backend`.

## Verifying the safety model manually

1. Open Config Deployment, modify a repo file in another window, then hit Apply — expect a "state changed, re-review" refusal (409), not a deploy.
2. Run any install — the confirmation dialog must list the exact command before anything executes; watch the job stream; check Diagnostics for the audit entry.
3. Grep the DOM and copied text for a seeded fake token — must be redacted everywhere.
