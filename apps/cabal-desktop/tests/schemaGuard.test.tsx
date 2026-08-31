// Component test: App's schema-version guard — shows the refresh prompt on a major-version
// mismatch and renders normally when the backend's envelope schema matches this build.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import App from "@/App";
import { buildHealthPayload, wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

function renderApp() {
  // retry: false on the client would be overridden by useHealth's own per-query retry: 2, but the
  // schema-mismatch listener fires synchronously on the first failed attempt regardless of retries,
  // so no need to wait out (or fake) the retry backoff for these assertions.
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

describe("App schema-version guard", () => {
  it("shows the refresh prompt when the backend schema major version does not match", async () => {
    server.use(
      http.get("/api/health", () =>
        HttpResponse.json(wrapEnvelope(buildHealthPayload(), { schema_version: "cabal-web.v3" })),
      ),
    );

    renderApp();

    expect(await screen.findByRole("alert")).toHaveTextContent("cabal-web.v3");
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
  });

  it("renders the normal shell when the backend schema version matches", async () => {
    server.use(
      http.get("/api/health", () => HttpResponse.json(wrapEnvelope(buildHealthPayload()))),
    );

    renderApp();

    expect(await screen.findByText("backend connected")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
