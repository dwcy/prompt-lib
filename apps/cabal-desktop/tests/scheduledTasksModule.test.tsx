import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { requireModule } from "@/modules/registry";
import { ScheduledTasksModule } from "@/modules/scheduled-tasks/ScheduledTasksModule";
import { buildConfirmationTicket, buildEffectPreview, wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

const TASK_PAYLOAD = {
  counts: { all: 2, active: 1, paused: 1, completed: 0 },
  providers: [
    {
      provider: "claude" as const,
      label: "Claude Desktop",
      detected: true,
      task_count: 1,
      source: "Local Desktop scheduled tasks",
      detail: "Cloud Routines are managed separately on claude.ai.",
      management_url: "https://claude.ai/code/routines",
    },
    {
      provider: "codex" as const,
      label: "Codex",
      detected: true,
      task_count: 1,
      source: "$CODEX_HOME/automations",
      detail: "Web-only ChatGPT tasks are managed separately in Scheduled.",
      management_url: "https://learn.chatgpt.com/docs/automations",
    },
  ],
  items: [
    {
      id: "claude:deploy-check",
      provider: "claude" as const,
      provider_task_id: "deploy-check",
      name: "Deploy check",
      description: "",
      prompt: "Check the deployment",
      schedule: "*/15 * * * *",
      schedule_kind: "recurring",
      status: "active",
      enabled: true,
      next_run_at: "2026-08-12T14:15:00Z",
      last_run_at: null,
      created_at: "2026-08-12T12:00:00Z",
      updated_at: "2026-08-12T12:00:00Z",
      workspace: "C:/projects/prompt-lib",
      execution_environment: "local",
      model: null,
      source: "claude_desktop_local",
      mirror_count: 2,
      can_delete: true,
    },
    {
      id: "codex:daily-review",
      provider: "codex" as const,
      provider_task_id: "daily-review",
      name: "Daily review",
      description: "",
      prompt: "Review open pull requests",
      schedule: "RRULE:FREQ=DAILY;BYHOUR=9;BYMINUTE=0",
      schedule_kind: "recurring",
      status: "paused",
      enabled: false,
      next_run_at: null,
      last_run_at: "2026-08-11T09:00:00Z",
      created_at: "2026-08-10T09:00:00Z",
      updated_at: "2026-08-11T09:00:00Z",
      workspace: "C:/projects/prompt-lib",
      execution_environment: "worktree",
      model: "gpt-5.6-terra",
      source: "codex_desktop_local",
      mirror_count: 1,
      can_delete: true,
    },
  ],
};

function renderModule() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ScheduledTasksModule />
    </QueryClientProvider>,
  );
}

describe("Scheduled Tasks module", () => {
  it("is registered under Agents", () => {
    expect(requireModule("scheduled_tasks").group).toBe("agents");
  });

  it("lists both providers, filters status, and prepares guarded deletion", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("/api/scheduled-tasks", () => HttpResponse.json(wrapEnvelope(TASK_PAYLOAD))),
      http.post("/api/actions/scheduled_tasks.delete/prepare", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildConfirmationTicket({
              action_id: "scheduled_tasks.delete",
              effect_preview: buildEffectPreview({
                summary: "Delete Codex scheduled task 'Daily review'",
                files_changed: ["automation.toml"],
                scopes: ["scheduled_tasks", "codex"],
                backup: "No backup",
                removals: ["Codex: Daily review (daily-review)"],
              }),
            }),
          ),
        ),
      ),
    );
    renderModule();

    expect((await screen.findAllByText("Deploy check")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Daily review").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Cloud routines ↗" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /paused 1/i }));
    expect(screen.queryAllByText("Deploy check")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: /Daily review/i }));
    await user.click(screen.getByRole("button", { name: "Delete task" }));

    const dialog = await screen.findByRole("alertdialog", { name: "Delete Scheduled Task" });
    expect(within(dialog).getByText("destructive")).toBeInTheDocument();
    expect(within(dialog).getByText("Codex: Daily review (daily-review)")).toBeInTheDocument();
  });
});
