using System.Net;
using System.Net.Http.Json;
using Api.Features.Health;
using Microsoft.AspNetCore.Mvc.Testing;

namespace Api.Tests.Features.Health;

/// <summary>
/// Drives the real host, not a mock. This is the smoke test FR-003 depends on: the scaffold is
/// only "runnable" if a request actually reaches an endpoint before any model has edited it.
/// </summary>
public sealed class HealthEndpointTests(WebApplicationFactory<Program> factory)
    : IClassFixture<WebApplicationFactory<Program>>
{
    [Fact]
    public async Task Health_returns_ok()
    {
        HttpClient client = factory.CreateClient();

        HttpResponseMessage response = await client.GetAsync("/health");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task Health_reports_healthy()
    {
        HttpClient client = factory.CreateClient();

        HealthResponse? body = await client.GetFromJsonAsync<HealthResponse>("/health");

        Assert.NotNull(body);
        Assert.Equal("healthy", body.Status);
    }
}
