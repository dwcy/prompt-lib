// Component test: ToolsModule's category rail (server-provided live counts), search/category/badge
// filtering (reflected in the "N of M tools" count), and the async status fill-in join (T042).
// VirtualDataTable can't render row cells under jsdom (@tanstack/react-virtual measures a real
// scroll container, always zero-sized in jsdom — see ToolsTable.tsx), so assertions here stick to
// the rail/filters/result-count, which render outside the virtualized table body; the join/filter
// logic itself is covered row-by-row in toolsFilters.test.ts.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { ToolsModule } from "@/modules/tools/ToolsModule";
import {
  buildToolCatalogItem,
  buildToolCatalogPayload,
  buildToolStatusEntry,
  wrapEnvelope,
} from "./msw/fixtures";
import { toolsCatalogHandler, toolsStatusHandler } from "./msw/handlers";
import { server } from "./msw/server";

function renderToolsModule() {
  const queryClient = new QueryClient();
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <ToolsModule />
    </QueryClientProvider>,
  );
  return { user };
}

const GIT = buildToolCatalogItem({
  key: "git",
  label: "Git",
  category: "System & VCS",
  install_channel: "package",
  badges: [],
});
const UV = buildToolCatalogItem({
  key: "uv",
  label: "uv",
  description: "Fast Python package manager, project manager, and tool runner.",
  category: "Package Managers",
  install_channel: "package",
  badges: ["recommended"],
});

describe("ToolsModule", () => {
  it("shows the category rail with the server-provided live counts per category", async () => {
    server.use(
      toolsCatalogHandler(buildToolCatalogPayload([GIT, UV])),
      toolsStatusHandler([
        buildToolStatusEntry("git", "installed"),
        buildToolStatusEntry("uv", "missing"),
      ]),
    );

    renderToolsModule();

    expect(await screen.findByRole("button", { name: "All (2)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "System & VCS (1)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Package Managers (1)" })).toBeInTheDocument();
    expect(await screen.findByText("2 of 2 tools")).toBeInTheDocument();
  });

  it("narrows the result count when searching by label, description, or key", async () => {
    server.use(
      toolsCatalogHandler(buildToolCatalogPayload([GIT, UV])),
      toolsStatusHandler([
        buildToolStatusEntry("git", "installed"),
        buildToolStatusEntry("uv", "missing"),
      ]),
    );
    const { user } = renderToolsModule();

    await screen.findByText("2 of 2 tools");
    await user.type(screen.getByRole("searchbox", { name: "Search tools" }), "python package");

    expect(await screen.findByText("1 of 2 tools")).toBeInTheDocument();
  });

  it("narrows the result count when a category rail entry is selected", async () => {
    server.use(
      toolsCatalogHandler(buildToolCatalogPayload([GIT, UV])),
      toolsStatusHandler([
        buildToolStatusEntry("git", "installed"),
        buildToolStatusEntry("uv", "missing"),
      ]),
    );
    const { user } = renderToolsModule();

    await screen.findByText("2 of 2 tools");
    await user.click(screen.getByRole("button", { name: "Package Managers (1)" }));

    expect(await screen.findByText("1 of 2 tools")).toBeInTheDocument();
  });

  it("narrows the result count when a live badge chip is toggled on", async () => {
    server.use(
      toolsCatalogHandler(buildToolCatalogPayload([GIT, UV])),
      toolsStatusHandler([
        buildToolStatusEntry("git", "installed"),
        buildToolStatusEntry("uv", "missing"),
      ]),
    );
    const { user } = renderToolsModule();

    await screen.findByText("2 of 2 tools");
    expect(screen.getByRole("button", { name: "recommended (1)" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "recommended (1)" }));

    expect(await screen.findByText("1 of 2 tools")).toBeInTheDocument();
  });

  it("renders the catalog result count before the slower status sweep resolves, then fills statuses in", async () => {
    let resolveStatus: (() => void) | null = null;
    const statusResolved = new Promise<void>((resolve) => {
      resolveStatus = resolve;
    });
    server.use(
      toolsCatalogHandler(buildToolCatalogPayload([GIT, UV])),
      http.get("/api/tools/status", async () => {
        await statusResolved;
        return HttpResponse.json(
          wrapEnvelope({
            items: [
              buildToolStatusEntry("git", "installed"),
              buildToolStatusEntry("uv", "missing"),
            ],
          }),
        );
      }),
    );
    const { user } = renderToolsModule();

    // Catalog metadata renders immediately: the result count is available before status resolves.
    expect(await screen.findByText("2 of 2 tools")).toBeInTheDocument();

    // While status is still unresolved, every row's status is the null "not yet arrived" fill-in
    // marker, so a status filter matches nothing yet.
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Filter by status" }),
      "installed",
    );
    expect(await screen.findByText("0 of 2 tools")).toBeInTheDocument();

    resolveStatus?.();

    // Once the status sweep resolves, the same filter now matches the tool whose status filled in.
    expect(await screen.findByText("1 of 2 tools")).toBeInTheDocument();
  });
});
