// Component test: Diagnostics renders persisted history filtered by severity and shows live
// diagnostic events from the SSE tail (T035).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { DiagnosticsModule } from "@/modules/diagnostics/DiagnosticsModule";
import { buildDiagnosticEvent, wrapEnvelope } from "./msw/fixtures";
import { diagnosticsStreamHandler } from "./msw/handlers";
import { server } from "./msw/server";

function renderDiagnostics() {
  const queryClient = new QueryClient();
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <DiagnosticsModule />
    </QueryClientProvider>,
  );
  return { user };
}

describe("DiagnosticsModule", () => {
  it("renders persisted history and re-filters by severity", async () => {
    server.use(
      diagnosticsStreamHandler([], { keepOpen: true }),
      http.get("/api/diagnostics", ({ request }) => {
        const severity = new URL(request.url).searchParams.get("severity");
        const events =
          severity === "error"
            ? [buildDiagnosticEvent({ id: 2, severity: "error", message: "boom" })]
            : [
                buildDiagnosticEvent({ id: 1, severity: "info", message: "nominal" }),
                buildDiagnosticEvent({ id: 2, severity: "error", message: "boom" }),
              ];
        return HttpResponse.json(wrapEnvelope({ events }));
      }),
    );
    const { user } = renderDiagnostics();

    expect(await screen.findByText("nominal")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "error" }));

    await screen.findByText("boom");
    expect(screen.queryByText("nominal")).not.toBeInTheDocument();
  });

  it("shows live diagnostic events from the SSE tail", async () => {
    server.use(
      http.get("/api/diagnostics", () => HttpResponse.json(wrapEnvelope({ events: [] }))),
      diagnosticsStreamHandler(
        [
          {
            event: "diagnostic",
            id: 1,
            data: buildDiagnosticEvent({ id: 1, severity: "warning", message: "live warning" }),
          },
        ],
        // Diagnostics streams never emit a terminal event (unlike job streams) — a clean close
        // makes useEventStream reconnect immediately with no backoff, hammering the mock
        // indefinitely. keepOpen mirrors the real backend's long-lived connection instead.
        { keepOpen: true },
      ),
    );

    renderDiagnostics();

    expect(await screen.findByText("live warning")).toBeInTheDocument();
  });
});
