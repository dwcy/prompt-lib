// Deploy-config tree behaviour: queueing a component's files (the checkbox handler used to read
// event.currentTarget inside the lazy state updater, which React has already nulled by then —
// the whole module crashed into its error boundary), filtering the tree down to one config group,
// and the file reader — diff, either side of an unchanged file, and markdown as a document.
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

const DIFF_TEXT = ["--- deployed/x", "+++ repo/x", "@@ -1 +1 @@", "-old line", "+new line"].join(
  "\n",
);

const MARKDOWN_SOURCE = "# Lessons\n\nKeep the terminal honest.\n";

function treeHandler() {
  return http.get("/api/config/tree", () => HttpResponse.json(wrapEnvelope(TREE)));
}

function diffHandler() {
  return http.get("/api/config/diff", ({ request }) =>
    HttpResponse.json(
      wrapEnvelope({
        target: "claude",
        rel_path: new URL(request.url).searchParams.get("path"),
        state: "changed",
        diff_text: DIFF_TEXT,
      }),
    ),
  );
}

function fileEnvelope(request: Request, overrides: Record<string, unknown>) {
  const params = new URL(request.url).searchParams;
  return wrapEnvelope({
    target: "claude",
    rel_path: params.get("path"),
    side: params.get("side"),
    abs_path: `C:/Users/dev/.claude/${params.get("path")}`,
    state: "unchanged",
    exists: true,
    binary: false,
    truncated: false,
    size_bytes: 18,
    markdown: null,
    ...overrides,
  });
}

function fileHandler() {
  return http.get("/api/config/file", ({ request }) => {
    const side = new URL(request.url).searchParams.get("side");
    return HttpResponse.json(
      fileEnvelope(request, {
        content: side === "deployed" ? "deployed body line" : "repo body line",
      }),
    );
  });
}

function markdownFileHandler() {
  return http.get("/api/config/file", ({ request }) =>
    HttpResponse.json(
      fileEnvelope(request, {
        content: MARKDOWN_SOURCE,
        markdown: {
          preamble: [],
          sections: [
            {
              level: 1,
              title: "Lessons",
              anchor: "lessons",
              blocks: [{ type: "paragraph", text: "Keep the terminal honest." }],
            },
          ],
        },
      }),
    ),
  );
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

function rowFor(relPath: string): HTMLElement {
  return screen.getByText(relPath).closest("li") as HTMLElement;
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

  it("shows a diff only once asked, not as a permanent panel", async () => {
    server.use(treeHandler(), diffHandler());
    const { user } = renderModule();

    await screen.findByText("skills/css/SKILL.md");
    expect(screen.queryByLabelText("Unified diff")).not.toBeInTheDocument();

    await user.click(within(rowFor("skills/css/SKILL.md")).getByRole("button", { name: "Diff" }));

    const dialog = await screen.findByRole("dialog", { name: "skills/css/SKILL.md contents" });
    expect(await within(dialog).findByLabelText("Unified diff")).toBeInTheDocument();
  });

  it("opens a file with no diff and switches between deployed and repo source", async () => {
    server.use(treeHandler(), fileHandler());
    const { user } = renderModule();

    await screen.findByText("skills/tui/SKILL.md");
    const row = rowFor("skills/tui/SKILL.md");
    expect(within(row).getByRole("button", { name: "Diff" })).toBeDisabled();

    await user.click(within(row).getByRole("button", { name: "View file" }));
    const dialog = await screen.findByRole("dialog", { name: "skills/tui/SKILL.md contents" });
    expect(await within(dialog).findByText("deployed body line")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("tab", { name: "Repo source" }));
    expect(await within(dialog).findByText("repo body line")).toBeInTheDocument();
  });

  it("renders a markdown file as a document, with raw behind a toggle", async () => {
    server.use(treeHandler(), markdownFileHandler());
    const { user } = renderModule();

    await screen.findByText("skills/tui/SKILL.md");
    await user.click(
      within(rowFor("skills/tui/SKILL.md")).getByRole("button", { name: "View file" }),
    );

    const dialog = await screen.findByRole("dialog", { name: "skills/tui/SKILL.md contents" });
    expect(await within(dialog).findByRole("heading", { name: "Lessons" })).toBeInTheDocument();
    expect(within(dialog).getByText("Keep the terminal honest.")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Raw markdown" }));
    expect(await within(dialog).findByText(/^# Lessons/)).toBeInTheDocument();
  });
});
