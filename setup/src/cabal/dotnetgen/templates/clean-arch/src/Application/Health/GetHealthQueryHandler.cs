namespace Application.Health;

/// <summary>
/// Handles <see cref="GetHealthQuery"/>. One handler per query - Commands mutate state and
/// Queries return data, and they never share a file (csharp.md).
/// </summary>
public sealed class GetHealthQueryHandler
{
    public HealthResponse Handle(GetHealthQuery query) => new("healthy");
}
