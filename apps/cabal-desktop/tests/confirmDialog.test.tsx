// Component test: useAction's prepare -> confirm -> execute flow through ConfirmDialog, including
// the 409 state_changed re-review path (FR-014) — driven through a minimal consuming harness since
// useAction has no reasonable host component of its own.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useAction } from "@/hooks/useAction";
import { useJobTrayStore } from "@/stores/jobTray";
import {
  buildConfirmationTicket,
  buildEffectPreview,
  buildErrorEnvelope,
  wrapEnvelope,
} from "./msw/fixtures";
import { server } from "./msw/server";

function ActionHarness({ actionId }: { actionId: string }) {
  const action = useAction(actionId);
  return (
    <div>
      <button type="button" onClick={() => action.prepare({ file: "x" })}>
        Prepare
      </button>
      <ConfirmDialog
        isOpen={action.phase !== "idle"}
        actionTitle="Apply config"
        ticket={action.ticket}
        phase={action.phase}
        reviewNotice={action.reviewNotice}
        error={action.error}
        onConfirm={action.confirm}
        onCancel={action.reset}
      />
      {action.phase === "succeeded" ? <p>Action succeeded: job {action.jobId ?? "none"}</p> : null}
    </div>
  );
}

function renderHarness(actionId = "config.apply") {
  const queryClient = new QueryClient();
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <ActionHarness actionId={actionId} />
    </QueryClientProvider>,
  );
  return { user };
}

describe("ConfirmDialog + useAction", () => {
  afterEach(() => {
    useJobTrayStore.getState().clear();
  });

  it("renders the effect preview with destructive styling when the ticket includes removals", async () => {
    server.use(
      http.post("/api/actions/:actionId/prepare", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildConfirmationTicket({
              effect_preview: buildEffectPreview({
                summary: "Remove 2 stale agents",
                commands: ["rm agents/old.md"],
                files_changed: ["configs/settings.json"],
                scopes: ["claude"],
                backup: "agents-backup",
                removals: ["agents/old.md", "agents/older.md"],
              }),
            }),
          ),
        ),
      ),
    );
    const { user } = renderHarness();

    await user.click(screen.getByRole("button", { name: "Prepare" }));

    expect(await screen.findByText("Remove 2 stale agents")).toBeInTheDocument();
    expect(screen.getByText("rm agents/old.md")).toBeInTheDocument();
    expect(screen.getByText("configs/settings.json")).toBeInTheDocument();
    expect(screen.getByText("claude")).toBeInTheDocument();
    expect(screen.getByText("agents-backup")).toBeInTheDocument();
    expect(screen.getByText("agents/old.md")).toBeInTheDocument();
    expect(screen.getByText("agents/older.md")).toBeInTheDocument();
    const dialog = screen.getByRole("alertdialog");
    expect(dialog.className).toContain("confirm-dialog--destructive");
  });

  it("confirms and executes successfully, surfacing the returned job id", async () => {
    server.use(
      http.post("/api/actions/:actionId/prepare", () =>
        HttpResponse.json(wrapEnvelope(buildConfirmationTicket())),
      ),
      http.post("/api/actions/:actionId/execute", () =>
        HttpResponse.json(wrapEnvelope({ job_id: "job-42" })),
      ),
    );
    const { user } = renderHarness();

    await user.click(screen.getByRole("button", { name: "Prepare" }));
    await screen.findByText("Deploy 3 changed files to ~/.claude");
    await user.click(screen.getByRole("button", { name: "Apply config" }));

    expect(await screen.findByText("Action succeeded: job job-42")).toBeInTheDocument();
  });

  it("re-prepares and shows the re-review notice when execute reports 409 state_changed", async () => {
    let prepareCallCount = 0;
    server.use(
      http.post("/api/actions/:actionId/prepare", () => {
        prepareCallCount += 1;
        const summary =
          prepareCallCount === 1
            ? "Deploy 3 changed files to ~/.claude"
            : "Deploy 4 changed files to ~/.claude (refreshed)";
        return HttpResponse.json(
          wrapEnvelope(
            buildConfirmationTicket({
              ticket_id: `ticket-${prepareCallCount}`,
              precondition_digest: `sha256:digest-${prepareCallCount}`,
              effect_preview: buildEffectPreview({ summary }),
            }),
          ),
        );
      }),
      http.post("/api/actions/:actionId/execute", () =>
        HttpResponse.json(
          buildErrorEnvelope({ code: "state_changed", message: "Backend state changed" }),
          { status: 409 },
        ),
      ),
    );
    const { user } = renderHarness();

    await user.click(screen.getByRole("button", { name: "Prepare" }));
    await screen.findByText("Deploy 3 changed files to ~/.claude");
    await user.click(screen.getByRole("button", { name: "Apply config" }));

    expect(
      await screen.findByText(
        "State changed since this preview was prepared. Review the updated effect before confirming.",
      ),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("Deploy 4 changed files to ~/.claude (refreshed)"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Deploy 3 changed files to ~/.claude")).not.toBeInTheDocument();
    expect(screen.queryByText("Action succeeded: job none")).not.toBeInTheDocument();
  });
});
