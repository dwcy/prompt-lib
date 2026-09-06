using Api.Endpoints;
using Application.Health;
using Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlite(builder.Configuration.GetConnectionString("Default")));
builder.Services.AddScoped<GetHealthQueryHandler>();

WebApplication app = builder.Build();

// One line per endpoint. Handlers are registered above; routing stays declarative here.
app.MapHealth();

app.Run();

/// <summary>Exposed so the integration tests can drive the real host via WebApplicationFactory.</summary>
public partial class Program;
