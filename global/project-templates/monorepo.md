## Questions

1. What is the monorepo structure?
   - .NET API + React/Next.js frontend
   - .NET API + Vue/Nuxt frontend
   - Node.js API + React/Next.js frontend
   - Python API + React/Next.js frontend
   - Full-stack with shared packages/libs
   - Other (describe)

2. Which monorepo tooling?
   - Turborepo
   - Nx
   - pnpm workspaces (no build orchestrator)
   - None / manual scripts

3. If this monorepo has a frontend app, which package manager should it use?
   - pnpm (recommended)
   - Bun
   - No frontend app

4. Is there a shared library / contracts project?
   - Shared TypeScript types between frontend and backend
   - Shared .NET class library
   - OpenAPI / generated client (e.g. Orval, NSwag)
   - None

5. How are environment configs managed?
   - `.env` files per workspace
   - Central `.env` at root
   - Docker Compose environment
   - Secrets manager (Azure Key Vault, AWS Secrets Manager)

6. How is the app deployed?
   - Docker Compose (local + prod)
   - Separate containers per service (Kubernetes / App Service)
   - Single container
   - Serverless

7. Is there a CI/CD pipeline already? (yes/no)
   - If yes: GitHub Actions / Azure DevOps / other?

---

## CLAUDE.md Template

# [Project Name] — Monorepo Developer Guide

## Structure

- **Backend:** [BACKEND STACK]
- **Frontend:** [FRONTEND STACK]
- **Shared:** [SHARED LAYER]
- **Monorepo tooling:** [TOOLING]
- **Frontend package manager:** [FRONTEND PACKAGE MANAGER]
- **Deployment:** [DEPLOYMENT APPROACH]

## Repository Layout

```
apps/
  api/             # Backend (.NET / Node / Python)
  web/             # Frontend (React / Vue / etc.)
packages/ (or libs/)
  shared-types/    # Shared contracts / TypeScript types
  ui/              # Shared component library (if any)
infra/             # Docker, K8s, IaC (Terraform / Bicep)
.github/
  workflows/       # CI/CD pipelines
```

## Working Across the Stack

- Always check both `apps/api` and `apps/web` when changing an API contract
- If the API response shape changes, update the shared types and regenerate the client
- Never call the backend URL directly from frontend components — use the generated client or a service layer

## Environment Setup

```bash
# Root
cp .env.example .env

# Start all services
docker-compose up

# Or run individually
cd apps/api && dotnet run        # or: uvicorn / node
cd apps/web && pnpm dev          # or: bun run dev
```

## Build & CI Rules

- All pull requests must pass both backend and frontend CI
- Do not merge if either `apps/api` or `apps/web` tests are red
- Shared package changes require bumping the version and updating all consumers
- Frontend and Node.js commands must use only `pnpm` or `bun`; never use `npm`, `npx`, or `yarn`
- New frontend work must use latest stable packages and verify current docs before adding version-specific APIs

## API Contract Rules

- API changes must be backward-compatible or versioned (`/api/v2/...`)
- Frontend should never parse raw strings from the API — use typed response models
- Breaking changes require a migration plan before merging

## Backend Conventions

> See `apps/api/CLAUDE.md` for detailed backend rules.

## Frontend Conventions

> See `apps/web/CLAUDE.md` for detailed frontend rules.

## What NOT to do

- Do not add backend logic to the frontend and vice versa
- Do not commit `.env` files or secrets
- Do not bypass the shared types layer with `any` or untyped API calls
- Do not run the entire test suite locally to check a small change — use workspace-scoped commands
