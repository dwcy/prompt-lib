namespace Api.Features.Health;

/// <summary>Liveness probe. A Query — it returns data and mutates nothing (csharp.md).</summary>
public static class HealthEndpoint
{
    /// <summary>Registers the slice's routes. Every slice exposes exactly one of these.</summary>
    public static IEndpointRouteBuilder MapHealth(this IEndpointRouteBuilder routes)
    {
        routes.MapGet("/health", () => Results.Ok(new HealthResponse("healthy")));
        return routes;
    }
}
