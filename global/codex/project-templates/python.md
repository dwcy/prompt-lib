## Questions

1. What is the project type?
   - REST API
   - CLI tool
   - Data Science / ML pipeline
   - Background worker / task queue
   - Library / package

2. Which framework? (based on type above)
   - FastAPI
   - Django + DRF
   - Flask
   - Typer / Click (CLI)
   - No framework (pure Python)

3. Which package manager?
   - uv (recommended)
   - Poetry
   - pip + requirements.txt
   - Conda

4. Which test framework?
   - pytest (recommended)
   - unittest

5. Are you using async/await throughout? (yes/no)

6. Which database / ORM (if any)?
   - SQLAlchemy (async)
   - SQLAlchemy (sync)
   - Django ORM
   - Tortoise ORM
   - No database

7. Python version? (e.g. 3.12, 3.13)

---

## AGENTS.md Template

# [Project Name] — Python Developer Guide

## Stack

- **Python:** [VERSION]
- **Project type:** [PROJECT TYPE]
- **Framework:** [FRAMEWORK]
- **Package manager:** [PACKAGE MANAGER]
- **Test framework:** [TEST FRAMEWORK]
- **Database / ORM:** [ORM]

## Project Structure

```
src/
  [package_name]/
    api/           # Routers / endpoints
    core/          # Config, settings, startup
    domain/        # Business logic, entities
    infra/         # DB, external clients
    schemas/       # Pydantic models (request/response)
tests/
  unit/
  integration/
```

## Code Conventions

- Use **type hints everywhere** — no untyped function signatures
- Use `from __future__ import annotations` in all files
- Prefer `dataclasses` or Pydantic `BaseModel` for data containers
- Use `pathlib.Path` instead of `os.path`
- Max line length: 88 (Black default)
- Format with **Black**, lint with **Ruff**

## Architecture Rules

- Business logic lives in `domain/` — never in routers or endpoints
- Settings loaded via `pydantic-settings` from environment variables only — no hardcoded config
- Use dependency injection (FastAPI `Depends`) for database sessions and services
- Never `import *`

## Async Rules (if applicable)

- All I/O-bound operations must be `async` — no blocking calls in async context
- Use `asyncio.gather` for concurrent work, not sequential awaits
- Database sessions must use `async with` context managers

## Testing Rules

- Use `pytest` with `pytest-asyncio` for async tests
- Use fixtures for database setup — never share state between tests
- Integration tests use a real database, not mocks
- `conftest.py` holds shared fixtures only

## What NOT to do

- Do not put SQL queries directly in routers
- Do not use mutable default arguments (`def f(x=[])`)
- Do not catch bare `Exception` — catch specific exceptions
- Do not use `print` for logging — use `logging` or `structlog`

## Build & Run

```bash
uv sync
uv run uvicorn src.[package_name].main:app --reload
uv run pytest
```
