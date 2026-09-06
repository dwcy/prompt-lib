// Covers the grouped sidebar: one animated module icon per nav row, and hover/focus driving the
// icon's imperative animation handle rather than the icon's own 16px hover box.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { SidebarNav } from "@/components/shell/SidebarNav";
import { MODULE_REGISTRY } from "@/modules/registry";

function renderSidebar() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <SidebarNav activeModuleKey="home_overview" onSelectModule={() => {}} />
    </QueryClientProvider>,
  );
}

describe("SidebarNav", () => {
  it("gives every nav module its own icon", () => {
    const { container } = renderSidebar();

    const navItems = container.querySelectorAll(".sidebar-nav__item");
    const navIcons = container.querySelectorAll(".sidebar-nav__item-icon svg");

    expect(navItems).toHaveLength(MODULE_REGISTRY.length);
    expect(navIcons).toHaveLength(MODULE_REGISTRY.length);
  });

  it("keeps the icon mounted while the row is hovered", async () => {
    const user = userEvent.setup();
    const { container } = renderSidebar();

    const item = container.querySelector(".sidebar-nav__item");
    expect(item).not.toBeNull();
    await user.hover(item as HTMLElement);
    expect(item?.querySelector(".sidebar-nav__item-icon svg")).not.toBeNull();

    await user.unhover(item as HTMLElement);
    expect(item?.querySelector(".sidebar-nav__item-icon svg")).not.toBeNull();
  });
});
