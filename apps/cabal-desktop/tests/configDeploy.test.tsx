// Deploy-config tree behaviour: queueing a component's files (the checkbox handler used to read
// event.currentTarget inside the lazy state updater, which React has already nulled by then —
// the whole module crashed into its error boundary), filtering the tree down to one config group,
// and reading a file that has no diff at all.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { ConfigDeployModule } from "@/modules/config-deploy/ConfigDeployModule";
import { wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

const TREE = {
  target: "claude",
  components: [
    {
      key: "skills",
      label: "skills/",
      group: "Skills",
      files: [
        { rel_path: "skills/tui/SKILL.md", state: "unchanged", diff_available: false },
        { rel_path: "skills/css/SKILL.md", state: "changed", diff_available: true },
      ],
    },
    {
      key: "agents",
      label: "agents/",
      group: "Agents",
      files: [{ rel_path: "agents/python-tester.md", state: "unchanged", diff_available: false }],
    },
  ],
  drift: {
    target: "claude",
    changed_count: 1,
    new_count: 0,
    unchanged_count: 2,
    extras_count: 0,
    computed_at: "2026-01-01T00:00:00Z",
    digest: "sha256:abc",
  },
};

function treeHandler() {
  return http.get("/api/config/tree", () => HttpResponse.json(wrapEnvelope(TREE)));
}

function fileHandler() {
  return http.get("/api/config/file", ({ request }) => {
    const params = new URL(request.url).searchParams;
    const side = params.get("side");
    return HttpResponse.json(
      wrapEnvelope({
        target: "claude",
        rel_path: params.get("path"),
        side,
        abs_path: `C:/Users/dev/.claude/${params.get("path")}`,
        state: "unchanged",
        exists: true,
        content: side === "deployed" ? "deployed body line" : "repo body line",
        binary: false,
        truncated: false,
        size_bytes: 18,
      }),
    );
  });
}

function renderModule() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <ConfigDeployModule />
    </QueryClientProvider>,
  );
  return { user };
}

describe("Deploy config tree", () => {
  it("queues every drifted file in a component from its header checkbox", async () => {
    server.use(treeHandler());
    const { user } = renderModule();

    await screen.findByText("skills/");
    await user.click(screen.getAllByRole("checkbox")[0]);

    expect(screen.getByText("1 file(s) ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply 1" })).toBeEnabled();
  });

  it("narrows the tree to one config group", async () => {
    server.use(treeHandler());
    const { user } = renderModule();

    await screen.findByText("agents/");
    await user.click(screen.getByRole("tab", { name: /Agents/ }));

    expect(screen.getByText("agents/")).toBeInTheDocument();
    expect(screen.queryByText("skills/")).not.toBeInTheDocument();
    // Nothing in Agents has drifted, so there is nothing to queue from here.
    expect(screen.getByRole("button", { name: "Select drift" })).toBeDisabled();
  });

  it("opens a file with no diff and switches between deployed and repo source", async () => {
    server.use(treeHandler(), fileHandler());
    const { user } = renderModule();

    await screen.findByText("skills/tui/SKILL.md");
    const row = screen.getByText("skills/tui/SKILL.md").closest("li") as HTMLElement;
    expect(within(row).getByRole("button", { name: "Diff" })).toBeDisabled();

    await user.click(within(row).getByRole("button", { name: "View file" }));
    const dialog = await screen.findByRole("dialog", { name: "skills/tui/SKILL.md contents" });
    expect(await within(dialog).findByText("deployed body line")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("tab", { name: "Repo source" }));
    expect(await within(dialog).findByText("repo body line")).toBeInTheDocument();
  });
});
