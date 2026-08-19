using Microsoft.EntityFrameworkCore;

namespace Api.Persistence;

/// <summary>The single EF Core context. Slices add their DbSets here as they are built.</summary>
public sealed class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options);
