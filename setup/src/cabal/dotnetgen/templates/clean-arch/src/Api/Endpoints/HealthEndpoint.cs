using Application.Health;

namespace Api.Endpoints;

/// <summary>Maps the health route onto its Application handler. The Api layer does no logic.</summary>
public static class HealthEndpoint
{
    public static IEndpointRouteBuilder MapHealth(this IEndpointRouteBuilder routes)
    {
        routes.MapGet("/health", (GetHealthQueryHandler handler) =>
            Results.Ok(handler.Handle(new GetHealthQuery())));
        return routes;
    }
}
