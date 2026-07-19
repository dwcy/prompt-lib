import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { ModelAssignmentsModule } from "@/modules/model-assignments/ModelAssignmentsModule";
import { wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

function renderModule() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <ModelAssignmentsModule />
    </QueryClientProvider>,
  );
  return { user };
}

describe("ModelAssignmentsModule", () => {
  it("stages only an approved changed model pin and exposes the active fleet filter", async () => {
    server.use(
      http.get("/api/models", () =>
        HttpResponse.json(
          wrapEnvelope({
            assignments: [
              {
                asset_kind: "agent",
                asset_name: "react-architect",
                pinned_model: "sonnet",
                resolved_to: "claude-sonnet-4-5",
                assignable_models: ["haiku", "sonnet", "opus"],
                repo_and_target_in_sync: true,
                target_model: "claude-sonnet-4-5",
                valid: true,
              },
            ],
            assignable_models: ["haiku", "sonnet", "opus"],
            counts: { total: 1, invalid: 0, out_of_sync: 0 },
          }),
        ),
      ),
    );
    const { user } = renderModule();

    const allFilter = await screen.findByRole("button", { name: "all" });
    expect(allFilter).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Review route change" })).toBeDisabled();

    const picker = screen.getByRole("combobox", { name: "Next repository pin" });
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "haiku",
      "sonnet",
      "opus",
    ]);

    await user.selectOptions(picker, "opus");

    expect(screen.getByRole("button", { name: "Review route change" })).toBeEnabled();
    expect(screen.getByText("1 route change(s) staged")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "agent" }));
    expect(screen.getByRole("button", { name: "agent" })).toHaveAttribute("aria-pressed", "true");
  });
});
