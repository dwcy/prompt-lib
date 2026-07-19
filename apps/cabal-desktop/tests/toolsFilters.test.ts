// Unit tests for the Tools module's pure helpers: the catalog/status async fill-in join, and the
// client-side search/category/channel/status/badge filtering + live counts (T042). VirtualDataTable
// can't render rows under jsdom (see ToolsTable.tsx / DiagnosticsHistoryTable.tsx's comment on the
// same @tanstack/react-virtual limitation), so the join/filter behavior is verified here directly
// rather than through rendered table cells.
import { describe, expect, it } from "vitest";
import {
  collectBadgeCounts,
  collectStatusCounts,
  EMPTY_TOOL_FILTERS,
  filterToolRows,
  joinToolsWithStatus,
} from "@/modules/tools/toolsFilters";
import { buildToolCatalogItem, buildToolStatusEntry } from "./msw/fixtures";

describe("joinToolsWithStatus", () => {
  it("marks a catalog item's status as null when the status sweep hasn't resolved it yet", () => {
    const items = [buildToolCatalogItem({ key: "git" })];

    const rows = joinToolsWithStatus(items, []);

    expect(rows[0].status).toBeNull();
  });

  it("fills in the matching status once the status sweep resolves for that key", () => {
    const items = [buildToolCatalogItem({ key: "git" })];
    const statusEntries = [buildToolStatusEntry("git", "installed")];

    const rows = joinToolsWithStatus(items, statusEntries);

    expect(rows[0].status?.state).toBe("installed");
  });

  it("leaves unrelated catalog items unaffected by another tool's resolved status", () => {
    const items = [
      buildToolCatalogItem({ key: "git" }),
      buildToolCatalogItem({ key: "uv", label: "uv" }),
    ];
    const statusEntries = [buildToolStatusEntry("git", "installed")];

    const rows = joinToolsWithStatus(items, statusEntries);

    expect(rows.find((row) => row.key === "uv")?.status).toBeNull();
  });
});

describe("filterToolRows", () => {
  const rows = joinToolsWithStatus(
    [
      buildToolCatalogItem({
        key: "git",
        label: "Git",
        category: "System & VCS",
        install_channel: "package",
        badges: [],
      }),
      buildToolCatalogItem({
        key: "uv",
        label: "uv",
        description: "Fast Python package manager.",
        category: "Package Managers",
        install_channel: "package",
        badges: ["recommended"],
      }),
      buildToolCatalogItem({
        key: "docker",
        label: "Docker",
        category: "Container & Cloud",
        install_channel: "desktop_app",
        badges: [],
      }),
    ],
    [
      buildToolStatusEntry("git", "installed"),
      buildToolStatusEntry("uv", "missing"),
      buildToolStatusEntry("docker", "update_available"),
    ],
  );

  it("returns every row when no filters are active", () => {
    expect(filterToolRows(rows, EMPTY_TOOL_FILTERS)).toHaveLength(3);
  });

  it("matches search text against the tool's label, description, or key", () => {
    const filtered = filterToolRows(rows, { ...EMPTY_TOOL_FILTERS, search: "python package" });

    expect(filtered.map((row) => row.key)).toEqual(["uv"]);
  });

  it("restricts rows to the selected category", () => {
    const filtered = filterToolRows(rows, { ...EMPTY_TOOL_FILTERS, category: "Package Managers" });

    expect(filtered.map((row) => row.key)).toEqual(["uv"]);
  });

  it("restricts rows to the selected install channel", () => {
    const filtered = filterToolRows(rows, { ...EMPTY_TOOL_FILTERS, channel: "desktop_app" });

    expect(filtered.map((row) => row.key)).toEqual(["docker"]);
  });

  it("restricts rows to the selected status", () => {
    const filtered = filterToolRows(rows, { ...EMPTY_TOOL_FILTERS, status: "update_available" });

    expect(filtered.map((row) => row.key)).toEqual(["docker"]);
  });

  it("restricts rows to the selected badge", () => {
    const filtered = filterToolRows(rows, { ...EMPTY_TOOL_FILTERS, badge: "recommended" });

    expect(filtered.map((row) => row.key)).toEqual(["uv"]);
  });

  it("excludes rows whose status hasn't resolved yet when a status filter is active", () => {
    const rowsWithPendingStatus = joinToolsWithStatus(
      [buildToolCatalogItem({ key: "git" })],
      [], // status sweep hasn't resolved this key yet
    );

    const filtered = filterToolRows(rowsWithPendingStatus, {
      ...EMPTY_TOOL_FILTERS,
      status: "installed",
    });

    expect(filtered).toHaveLength(0);
  });
});

describe("collectBadgeCounts", () => {
  it("counts how many rows carry each badge", () => {
    const rows = joinToolsWithStatus(
      [
        buildToolCatalogItem({ key: "uv", badges: ["recommended"] }),
        buildToolCatalogItem({ key: "bun", badges: ["recommended"] }),
        buildToolCatalogItem({ key: "git", badges: [] }),
      ],
      [],
    );

    const counts = collectBadgeCounts(rows);

    expect(counts.get("recommended")).toBe(2);
    expect(counts.has("git")).toBe(false);
  });
});

describe("collectStatusCounts", () => {
  it("counts resolved statuses only, ignoring rows still awaiting the status sweep", () => {
    const rows = joinToolsWithStatus(
      [buildToolCatalogItem({ key: "git" }), buildToolCatalogItem({ key: "uv" })],
      [buildToolStatusEntry("git", "installed")],
    );

    const counts = collectStatusCounts(rows);

    expect(counts.get("installed")).toBe(1);
    expect(counts.get("missing")).toBeUndefined();
  });
});
