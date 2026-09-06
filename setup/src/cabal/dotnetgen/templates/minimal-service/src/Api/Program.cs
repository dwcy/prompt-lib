using Api.Features.Health;
using Api.Persistence;
using Microsoft.EntityFrameworkCore;

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlite(builder.Configuration.GetConnectionString("Default")));

WebApplication app = builder.Build();

// One line per feature. No mediator: the endpoint calls what it needs directly.
app.MapHealth();

app.Run();

/// <summary>Exposed so the integration tests can drive the real host via WebApplicationFactory.</summary>
public partial class Program;
