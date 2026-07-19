import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { ModuleSwitcher } from "@/components/shell/ModuleSwitcher";
import { VirtualDataTable } from "@/components/VirtualDataTable";

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getTotalSize: () => count * 36,
    getVirtualItems: () =>
      Array.from({ length: count }, (_, index) => ({
        index,
        key: index,
        start: index * 36,
        size: 36,
      })),
  }),
}));

vi.mock("@/api/health", () => ({
  useHealth: () => ({ data: undefined, isError: false }),
}));

const ROWS = [
  { id: "alpha", label: "Alpha" },
  { id: "beta", label: "Beta" },
];

function SelectionHarness() {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set(["alpha"]));

  return (
    <VirtualDataTable
      rows={ROWS}
      columns={[{ key: "label", header: "Name", render: (row) => row.label }]}
      getRowId={(row) => row.id}
      selectedIds={selectedIds}
      onSelectRow={(id, selected) =>
        setSelectedIds((current) => {
          const next = new Set(current);
          if (selected) next.add(id);
          else next.delete(id);
          return next;
        })
      }
    />
  );
}

describe("shared workspace interactions", () => {
  it("selects and clears every visible table row from a tri-state header control", async () => {
    const user = userEvent.setup();
    render(<SelectionHarness />);

    const selectAll = screen.getByRole("checkbox", { name: "Select all rows" });
    expect(selectAll).toBePartiallyChecked();

    await user.click(selectAll);

    expect(screen.getByRole("checkbox", { name: "Clear row selection" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Select alpha" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Select beta" })).toBeChecked();

    await user.click(screen.getByRole("checkbox", { name: "Clear row selection" }));

    expect(screen.getByRole("checkbox", { name: "Select all rows" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Select alpha" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Select beta" })).not.toBeChecked();
  });

  it("exposes the visually highlighted workspace-map result to assistive technology", async () => {
    const user = userEvent.setup();
    render(<ModuleSwitcher activeModuleKey="overview" onSelectModule={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Find a Cabal module" }));

    const search = screen.getByRole("searchbox", { name: "Search Cabal modules" });
    const activeResultId = search.getAttribute("aria-activedescendant");
    expect(search).toHaveAttribute("aria-controls", "module-switcher-results");
    expect(activeResultId).not.toBeNull();
    expect(document.getElementById(activeResultId ?? "")).toBeInTheDocument();
  });
});
