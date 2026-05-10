## Questions

Ask these in order. Skip irrelevant ones based on prior answers.

1. What is the project type?
   - Web API (ASP.NET Core minimal or controller-based)
   - Background Worker / Service Bus consumer
   - Class Library / NuGet package
   - Console / CLI tool
   - Blazor app

2. What architecture pattern?
   - Clean Architecture (Domain / Application / Infrastructure / Presentation layers)
   - Vertical Slice Architecture (feature folders)
   - Minimal / flat (no strict layering)

3. Which ORM / data access?
   - Entity Framework Core (code-first)
   - Entity Framework Core (db-first)
   - Dapper
   - No ORM / raw ADO.NET
   - No database

4. Which test framework?
   - xUnit (recommended)
   - NUnit
   - MSTest

5. Any key libraries in use? (select all that apply)
   - MediatR (CQRS / mediator pattern)
   - FluentValidation
   - AutoMapper / Mapster
   - Serilog / NLog
   - Polly (resilience)
   - MassTransit / NServiceBus

6. What .NET version? (e.g. .NET 9, .NET 8)

7. Are you using nullable reference types? (yes/no)

8. Do you want file-scoped namespaces enforced? (yes/no)

9. Apply the standard `.editorconfig` for this project? (yes/no)
   - Enforces LF line endings, 4-space indent for C#, file-scoped namespaces, xUnit rules, CA/IDE diagnostics
   - Template is at `~/.claude/git/.editorconfig` — copy it to the project root

---

## CLAUDE.md Template

# [Project Name] — .NET Developer Guide

## Stack

- **Runtime:** [.NET VERSION]
- **Project type:** [PROJECT TYPE]
- **Architecture:** [ARCHITECTURE PATTERN]
- **ORM:** [ORM CHOICE]
- **Test framework:** [TEST FRAMEWORK]
- **Key libraries:** [LIBRARIES LIST]

## Project Structure

```
src/
  [ProjectName].Domain/          # Entities, value objects, domain events
  [ProjectName].Application/     # Use cases, commands, queries, interfaces
  [ProjectName].Infrastructure/  # EF Core, external services, repositories
  [ProjectName].Api/             # Controllers / minimal API endpoints
tests/
  [ProjectName].UnitTests/
  [ProjectName].IntegrationTests/
```

> Adjust the above to match your actual structure.

## Code Conventions

- Use **file-scoped namespaces** (`namespace Foo;` not `namespace Foo { }`)
- Enable **nullable reference types** — never suppress warnings without a comment explaining why
- Prefer **primary constructors** for simple dependency injection (C# 12+)
- Use `record` for immutable DTOs and value objects
- Use `sealed` on classes not designed for inheritance
- Do not use `var` when the type is not obvious from the right-hand side

## Architecture Rules

### Clean Architecture (if applicable)
- Domain layer has **zero external dependencies** — no EF Core, no HTTP clients
- Application layer depends only on Domain — never on Infrastructure
- Infrastructure implements interfaces defined in Application
- Never reference `DbContext` directly in Application — use repository interfaces

### CQRS with MediatR (if applicable)
- One file per Command/Query and its Handler
- Commands mutate state, Queries return data — never mix
- Validation lives in a `ValidationBehavior` pipeline, not inside handlers

## Testing Rules

- Unit tests cover domain logic and application handlers in isolation
- Integration tests use a real database (TestContainers or SQLite in-memory)
- Do **not** mock `DbContext` — use a real test database
- Test method naming: `MethodName_Scenario_ExpectedResult`

## What NOT to do

- Do not put business logic in controllers or minimal API endpoints
- Do not call `SaveChanges` inside domain entities
- Do not use `static` classes for business logic
- Do not return `IEnumerable<T>` from repositories — return `List<T>` or `IReadOnlyList<T>`

## Code Style Tooling

- `.editorconfig` — enforces formatting rules at editor and build time (4-space indent for C#, file-scoped namespaces, xUnit diagnostics, CA/IDE severities)
- `.gitattributes` — LF line endings for all source files, CRLF for `.bat`/`.cmd`/`.ps1`, binary handling for images and build artifacts
- Git hooks — `commit-msg` enforces conventional commits, `pre-commit` runs `dotnet format`, `pre-push` runs `dotnet test`

> To apply all three: run `/git init` and choose to apply the template when prompted.

## Build & Run

```bash
dotnet build
dotnet test
dotnet run --project src/[ProjectName].Api
```
