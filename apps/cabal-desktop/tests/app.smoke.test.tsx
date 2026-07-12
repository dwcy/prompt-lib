// Smoke test: <App /> renders the shell (nav + health strip) under a QueryClientProvider.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import App from "@/App";
import { server } from "./msw/server";

function mockHealthyBackend() {
  server.use(
    http.get("/api/health", () =>
      HttpResponse.json({
        schema_version: "cabal-web.v2",
        captured_at: "2026-01-01T00:00:00Z",
        status: "ok",
        source: "system",
        stale: false,
        precondition_digest: null,
        data: { version: "0.0.0-test", started_at: "2026-01-01T00:00:00Z", modules: [] },
        error: null,
      }),
    ),
  );
}

function renderApp() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

describe("App", () => {
  it("renders the app name", () => {
    mockHealthyBackend();
    renderApp();

    expect(screen.getByRole("heading", { name: "Cabal" })).toBeInTheDocument();
  });
});
