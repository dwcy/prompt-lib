// Component test: the header health strip — label per backend state and the module breakdown
// dialog it opens on click.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { HealthPayload } from "@/api/schemas";
import { HealthStrip } from "@/components/shell/HealthStrip";
import { buildHealthPayload, buildModuleHealth, wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

function renderStrip(payload: HealthPayload) {
  server.use(http.get("/api/health", () => HttpResponse.json(wrapEnvelope(payload))));
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <HealthStrip />
    </QueryClientProvider>,
  );
}

describe("HealthStrip", () => {
  it("reads 'backend connected' when no module needs attention", async () => {
    renderStrip(
      buildHealthPayload(0, { modules: [buildModuleHealth({ module: "home_overview" })] }),
    );

    expect(await screen.findByText("backend connected")).toBeInTheDocument();
  });

  it("reads 'backend degraded' and counts the modules needing attention", async () => {
    renderStrip(
      buildHealthPayload(0, {
        modules: [
          buildModuleHealth({ module: "home_overview" }),
          buildModuleHealth({ module: "tools", state: "degraded", detail: "slow collector" }),
        ],
      }),
    );

    expect(await screen.findByText("backend degraded")).toBeInTheDocument();
    expect(screen.getByText(/1 module need/)).toBeInTheDocument();
  });

  it("opens a dialog listing every module, attention first", async () => {
    const user = userEvent.setup();
    renderStrip(
      buildHealthPayload(0, {
        modules: [
          buildModuleHealth({ module: "home_overview" }),
          buildModuleHealth({ module: "tools", state: "failed", detail: "router not mounted" }),
        ],
      }),
    );

    await user.click(await screen.findByRole("button", { name: /backend degraded/ }));

    const dialog = await screen.findByRole("dialog", { name: "Modules" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("1 of 2 modules need attention.")).toBeInTheDocument();

    const rows = screen.getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Tools Catalog");
    expect(rows[0]).toHaveTextContent("router not mounted");
    expect(rows[1]).toHaveTextContent("Home Overview");
  });

  it("closes the dialog on Escape", async () => {
    const user = userEvent.setup();
    renderStrip(
      buildHealthPayload(0, { modules: [buildModuleHealth({ module: "home_overview" })] }),
    );

    await user.click(await screen.findByRole("button", { name: /backend connected/ }));
    expect(await screen.findByRole("dialog", { name: "Modules" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
