using Microsoft.EntityFrameworkCore;

namespace Infrastructure.Persistence;

/// <summary>
/// The EF Core context. It lives in Infrastructure so the Domain stays free of persistence
/// concerns - that separation is the whole point of this template.
/// </summary>
public sealed class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options);
