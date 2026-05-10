# .NET Integration Test — Create or Refactor

Apply the following conventions whenever writing or refactoring integration tests for a .NET API project.

---

## 1. Test Framework: TUnit

Default to [TUnit](https://tunit.dev). Do not use xUnit or NUnit unless the project already uses them.

Required packages for a new test project:
```xml
<PackageReference Include="TUnit" Version="*" />
<PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="*" />
<PackageReference Include="Testcontainers" Version="*" />          <!-- if DB is needed -->
<PackageReference Include="Testcontainers.PostgreSql" Version="*" /> <!-- swap per DB engine -->
```

---

## 2. Test Project Structure

Mirror the real project's folder structure exactly. If the production code lives at:

```
src/MyApi/Features/Products/Services/ProductUpdateService.cs
```

The test file lives at:

```
tests/MyApi.Tests/Features/Products/ProductUpdateTests.cs
```

Rules:
- One test class per feature/use-case, not per class.
- Name test classes after the feature being tested: `ProductUpdateTests`, `OrderCheckoutTests`.
- Never name a test class after an implementation detail (`ProductUpdateServiceTests`).
- Place shared infrastructure in `tests/MyApi.Tests/Infrastructure/`.

```
tests/
  MyApi.Tests/
    Infrastructure/
      ApiFactory.cs           ← WebApplicationFactory wrapper
      TestBase.cs             ← shared base with helpers
      GlobalUsings.cs
    Features/
      Products/
        ProductUpdateTests.cs
        ProductRetrievalTests.cs
      Orders/
        OrderCheckoutTests.cs
```

---

## 3. AAA Pattern

Every test follows Arrange → Act → Assert with a blank line between each phase. No exceptions.

```csharp
[Test]
public async Task Update_product_price_reflects_in_subsequent_retrieval()
{
    // Arrange
    var product = await InitSetup.CreateProductAsync(Client, name: "Widget", price: 10.00m);
    var request = new UpdateProductPriceRequest { Price = 15.00m };

    // Act
    var response = await Client.PatchAsJsonAsync($"/products/{product.Id}/price", request);

    // Assert
    await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.OK);
    var updated = await Client.GetFromJsonAsync<ProductResponse>($"/products/{product.Id}");
    await Assert.That(updated!.Price).IsEqualTo(15.00m);
}
```

- Label each phase with a `// Arrange`, `// Act`, `// Assert` comment — these are structural, not explanatory.
- Keep assertions focused on **business outcomes**, not HTTP mechanics unless the status code is the business outcome.

---

## 4. Shared Test Infrastructure

### ApiFactory

Wraps `WebApplicationFactory<TEntryPoint>`. Owns the lifetime of the test server and any containers.

```csharp
/// <summary>
/// Spins up the full API in-process with a real database via Testcontainers.
/// Shared across the entire test session for speed.
/// </summary>
public class ApiFactory : WebApplicationFactory<Program>, IAsyncInitializer
{
    private readonly PostgreSqlContainer _db = new PostgreSqlBuilder().Build();

    public async Task InitializeAsync()
    {
        await _db.StartAsync();
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<DbContextOptions<AppDbContext>>();
            services.AddDbContext<AppDbContext>(options =>
                options.UseNpgsql(_db.GetConnectionString()));
        });
    }

    public override async ValueTask DisposeAsync()
    {
        await _db.DisposeAsync();
        await base.DisposeAsync();
    }
}
```

### TestBase

Base class every test class inherits. Receives the shared factory via TUnit's `ClassDataSource`.

```csharp
/// <summary>
/// Base class providing a configured HttpClient and shared setup helpers.
/// </summary>
[ClassDataSource<ApiFactory>(Shared = SharedType.PerTestSession)]
public abstract class TestBase(ApiFactory factory)
{
    protected HttpClient Client { get; } = factory.CreateClient();
}
```

---

## 5. InitSetup — Shared Feature Setup

When multiple tests in the same feature folder share common operations (creating seed data, performing a prerequisite request), extract them into a static `InitSetup` class inside that feature folder.

```
tests/MyApi.Tests/Features/Products/InitSetup.cs
tests/MyApi.Tests/Features/Orders/InitSetup.cs
```

```csharp
/// <summary>
/// Reusable setup operations shared across Product tests.
/// </summary>
internal static class InitSetup
{
    internal static async Task<ProductResponse> CreateProductAsync(
        HttpClient client,
        string name = "Test Product",
        decimal price = 9.99m)
    {
        var request = new CreateProductRequest { Name = name, Price = price };
        var response = await client.PostAsJsonAsync("/products", request);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<ProductResponse>()
               ?? throw new InvalidOperationException("No product returned.");
    }

    internal static async Task<ProductResponse> GetProductAsync(HttpClient client, Guid id)
    {
        var response = await client.GetAsync($"/products/{id}");
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<ProductResponse>()
               ?? throw new InvalidOperationException("Product not found.");
    }
}
```

Rules for `InitSetup`:
- Only add a method here when **two or more tests** in the same feature need it.
- Methods must be `internal static async Task<T>` — no state.
- Accept `HttpClient` as the first parameter; optional named parameters for variations.
- Never put assertions inside `InitSetup` — it is setup, not a test.

---

## 6. Writing Test Classes

```csharp
/// <summary>
/// Integration tests for the product update use-cases.
/// </summary>
public class ProductUpdateTests(ApiFactory factory) : TestBase(factory)
{
    [Test]
    public async Task Updating_price_returns_200_and_persists_change()
    {
        // Arrange
        var product = await InitSetup.CreateProductAsync(Client);
        var request = new UpdateProductPriceRequest { Price = 25.00m };

        // Act
        var response = await Client.PatchAsJsonAsync($"/products/{product.Id}/price", request);

        // Assert
        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.OK);
        var retrieved = await InitSetup.GetProductAsync(Client, product.Id);
        await Assert.That(retrieved.Price).IsEqualTo(25.00m);
    }

    [Test]
    public async Task Updating_price_to_negative_returns_400()
    {
        // Arrange
        var product = await InitSetup.CreateProductAsync(Client);
        var request = new UpdateProductPriceRequest { Price = -1.00m };

        // Act
        var response = await Client.PatchAsJsonAsync($"/products/{product.Id}/price", request);

        // Assert
        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.BadRequest);
    }
}
```

---

## 7. Test Naming Convention

Use plain English sentences that describe the **business behaviour**:

```
Updating_price_returns_200_and_persists_change        ✓
Update_product_price_reflects_in_subsequent_retrieval ✓
ProductUpdateService_UpdateAsync_Returns200           ✗  (implementation detail)
Test1                                                 ✗
```

Format: `<Context>_<action>_<expected outcome>` — underscores, lowercase except proper nouns.

---

## 8. What to Test

Focus on **use-cases and business rules**, not code paths:

| Test this | Not this |
|---|---|
| A checkout with an expired voucher returns 422 | `VoucherValidator.IsExpired()` returns true |
| Creating a product with a duplicate SKU returns 409 | The repository throws `DuplicateKeyException` |
| A fulfilled order cannot be cancelled | `OrderStateMachine` transition logic |
| The response body contains the correct resource URL | JSON serialisation of a DTO |

Avoid:
- Tests that only verify a method was called (mock-behavior assertions).
- Tests that duplicate validation already enforced by the type system.
- Happy-path-only suites — always add at least one sad-path per use-case.

---

## 9. GlobalUsings.cs

All `using` statements go in `GlobalUsings.cs` at the test project root. Never add usings to individual test files.

```csharp
global using System.Net;
global using System.Net.Http.Json;
global using Microsoft.Extensions.DependencyInjection;
global using TUnit.Core;
global using MyApi.Tests.Infrastructure;
```

---

## 10. Size and Responsibility Check

Before finishing, review the test class:

- If a test class exceeds **~150 lines**, it is likely covering more than one use-case. Stop and ask:
  > "This test class is getting large. Should we split it by use-case before continuing?"

- If `InitSetup` exceeds **~80 lines**, it is accumulating too many concerns. Stop and ask:
  > "InitSetup is growing. Should we break it into more focused helpers?"
