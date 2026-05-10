# .NET Class — Create or Refactor

Apply the following conventions whenever creating a new class or refactoring an existing one in a .NET project.

---

## 1. File Placement

Place every file inside a feature/context-based folder tree:

```
Features/<Domain>/<Layer>/<ClassName>.cs
```

Examples:
- `Features/Products/Services/ProductUpdateService.cs`
- `Features/Orders/Repositories/OrderRepository.cs`
- `Features/Payments/Adapters/StripeAdapter.cs`
- `Features/Products/Models/ProductUpdateRequest.cs`

Valid layer folder names: `Services`, `Repositories`, `Adapters`, `Models`, `Requests`, `Responses`, `Handlers`.

Whenever a new feature domain folder is created (e.g. `Features/Products/`), always also create these sibling folders, even if they remain empty:

```
Features/<Domain>/Scripts/
Features/<Domain>/References/
Features/<Domain>/Assets/
```

Use a `.gitkeep` file in each empty folder to ensure it is tracked by git.

**Scripts/** — feature-scoped automation and tooling. Examples: SQL migration scripts, seed data scripts, PowerShell/Bash helpers for local dev, scaffolding scripts tied to this domain.

When writing scripts in this folder, follow these conventions so they work reliably in automated and agentic contexts:

- **No interactive prompts.** Accept all input via flags, environment variables, or stdin. A script that blocks on a TTY prompt will hang. Emit a clear error with usage guidance instead:
  ```
  Error: --env is required. Options: development, staging, production.
  Usage: migrate.ps1 --env staging --tag v1.2.3
  ```
- **Document with `--help`.** Include a brief description, all flags, and usage examples. Keep it concise — it must be readable at a glance.
- **Structured output.** Prefer JSON or CSV over free-form text so output is composable with other tools. Send data to stdout and diagnostics/progress to stderr.
- **Idempotent by default.** Agents and pipelines may retry. "Create if not exists" is safer than "create and fail on duplicate."
- **Dry-run flag.** For destructive or stateful operations (drops, deletes, migrations) add a `--dry-run` flag to preview without applying.
- **Meaningful exit codes.** Use distinct codes per failure type (e.g. `1` = invalid args, `2` = not found, `3` = auth failure) and document them in `--help`.
- **Pin versions.** If a script invokes external tools, pin the version (e.g. `dotnet-ef@8.0.0`) so behaviour is reproducible.
- **Predictable output size.** If a script may emit large output, default to a summary and support `--output <file>` or pagination flags so the caller can retrieve more when needed.

**References/** — external documentation and specification artefacts that inform this feature. Examples: API contracts (OpenAPI/WSDL), third-party vendor docs, architecture decision records (ADRs), Confluence/Notion exports, PDF specs.

**Assets/** — static files consumed by or produced for this feature. Examples: email templates, report templates (RDLC/XLSX), sample import/export files, test fixtures, images or icons specific to this domain.

---

## 2. Naming Conventions

- Suffix classes by role: `Service`, `Repository`, `Adapter`, `Request`, `Response`, `Handler`
- Keep entity/domain names **pure** — no suffix: `Product.cs`, `Order.cs`, `Invoice.cs`
- Interface mirrors the class: `IProductUpdateService`, `IOrderRepository`

---

## 3. Top-Level Usings (`GlobalUsings.cs`)

- **Never** place `using` statements at the top of individual files.
- All usings go into `GlobalUsings.cs` at the project root.
- If `GlobalUsings.cs` does not exist in the target project, create it:

```csharp
global using System;
global using System.Collections.Generic;
// add further usings here
```

- Add any new namespaces required by the class to `GlobalUsings.cs`, not to the class file.

---

## 4. Primary Constructor (Top-Level Class Construct)

Use C# primary constructors for dependency injection. No `readonly` fields, no private setters.

```csharp
/// <summary>
/// Handles update operations for the Product aggregate.
/// </summary>
public class ProductUpdateService(
    IProductRepository productRepository,
    ILogger<ProductUpdateService> logger) : IProductUpdateService
{
    public async Task UpdateAsync(ProductUpdateRequest request) { ... }
}
```

Never write this pattern:
```csharp
// ❌ old style
private readonly IProductRepository _productRepository;
public ProductUpdateService(IProductRepository productRepository)
{
    _productRepository = productRepository;
}
```

---

## 5. Interface Requirement

Every `Service`, `Repository`, and `Adapter` **must** have a corresponding interface.

- Declare all public methods in the interface.
- Place the interface in the same feature folder or a sibling `Interfaces/` subfolder.

```csharp
public interface IProductUpdateService
{
    Task UpdateAsync(ProductUpdateRequest request);
}
```

---

## 6. Dependency Registration

After creating or modifying a class, confirm it is registered in DI.

- Prefer a dedicated extension method per feature over polluting `Program.cs`:

```csharp
public static class ProductFeatureExtensions
{
    public static IServiceCollection AddProductFeature(this IServiceCollection services)
    {
        services.AddScoped<IProductUpdateService, ProductUpdateService>();
        services.AddScoped<IProductRepository, ProductRepository>();
        return services;
    }
}
```

- Lifetimes: `AddScoped` for request-scoped work, `AddSingleton` for stateless/thread-safe, `AddTransient` rarely.

---

## 7. XML Summary

Every class and interface must have an XML doc summary:

```csharp
/// <summary>
/// Persists and retrieves Product entities from the database.
/// </summary>
public class ProductRepository(...) : IProductRepository { ... }
```

---

## 8. Size Check

Before finishing, count the lines in the class.

- If the class exceeds **~200 lines** or clearly owns more than one responsibility, **stop** and ask:

> "This class is getting large. Should we refactor it before continuing?"

Do not silently continue adding to an oversized class.
