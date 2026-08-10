import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { useKnowledgeGraph } from "@/api/knowledge";
import { KnowledgeModule } from "@/modules/knowledge/KnowledgeModule";
import { wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

vi.mock("@/modules/knowledge/GraphCanvas", () => ({
  GraphCanvas: ({
    graph,
    onSelect,
  }: {
    graph: { nodes: Array<{ id: string; label: string }> };
    onSelect: (node: unknown) => void;
  }) => (
    <section aria-label="Knowledge graph fixture">
      {graph.nodes.map((node) => (
        <button key={node.id} type="button" onClick={() => onSelect(node)}>
          {node.label}
        </button>
      ))}
    </section>
  ),
}));

const COUNTS = {
  nodes: 1,
  edges: 0,
  by_type: { agent: 1 },
  by_relation: {},
  findings_by_severity: {},
};

function renderModule() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <KnowledgeModule />
    </QueryClientProvider>,
  );
  return { user };
}

function GraphProbe() {
  const query = useKnowledgeGraph({ query: "", type: "", relation: "" });
  if (query.isPending) return <span>loading</span>;
  if (query.isError) return <span>{query.error.message}</span>;
  return <span>{query.data.nodes.map((node) => node.label).join(", ")}</span>;
}

describe("KnowledgeModule", () => {
  it("loads every graph page and merges cross-page relationships", async () => {
    const cursors: Array<string | null> = [];
    server.use(
      http.get("/api/knowledge/graph", ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        cursors.push(cursor);
        const firstPage = cursor === null;
        return HttpResponse.json(
          wrapEnvelope({
            available: true,
            generated_at: "2026-07-13T12:00:00Z",
            nodes: [
              {
                id: firstPage ? "agent:first" : "agent:second",
                type: "agent",
                label: firstPage ? "First page" : "Second page",
                resource: "global/agents/example.md",
                doc: "",
                tags: [],
                metrics: {},
              },
            ],
            edges: firstPage
              ? [
                  {
                    id: "cross-page",
                    from: "agent:first",
                    to: "agent:second",
                    target_ref: "agent:second",
                    relation: "delegates_to",
                    confidence: "",
                    reason: "",
                    evidence: [],
                  },
                ]
              : [],
            counts: { ...COUNTS, nodes: 2, edges: 1 },
            next_cursor: firstPage ? "900" : null,
            total_nodes: 2,
            total_edges: 1,
          }),
        );
      }),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <GraphProbe />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("First page, Second page")).toBeInTheDocument();
    expect(cursors).toEqual([null, "900"]);
  });

  it("hands a search result into a context pack and honors the selected budget", async () => {
    const requestedBudgets: string[] = [];
    server.use(
      http.get("/api/knowledge", () =>
        HttpResponse.json(
          wrapEnvelope({
            available: true,
            repo_root: "C:/projects/prompt-lib",
            bundle_root: "docs/okf/prompt-lib",
            index_path: "docs/okf/index.sqlite",
            usage_path: "docs/okf/usage.jsonl",
            generated_at: "2026-07-13T12:00:00Z",
            index_available: true,
            semantic_available: false,
            usage_count: 4,
            counts: COUNTS,
            digest: "sha256:knowledge",
          }),
        ),
      ),
      http.get("/api/knowledge/graph", () =>
        HttpResponse.json(
          wrapEnvelope({
            available: true,
            generated_at: "2026-07-13T12:00:00Z",
            nodes: [
              {
                id: "agent:react-architect",
                type: "agent",
                label: "React architect",
                resource: "global/agents/react-architect.md",
                doc: "Owns React work",
                tags: ["frontend"],
                metrics: { incoming: 0, outgoing: 0 },
              },
            ],
            edges: [],
            counts: COUNTS,
            next_cursor: null,
            total_nodes: 1,
            total_edges: 0,
          }),
        ),
      ),
      http.get("/api/knowledge/search", ({ request }) => {
        const query = new URL(request.url).searchParams.get("q") ?? "";
        return HttpResponse.json(
          wrapEnvelope({
            available: true,
            mode: "fulltext",
            query,
            status: "ok",
            message: "",
            results: [
              {
                id: "spec:config-deploy",
                type: "spec",
                title: "Configuration deployment",
                resource: "specs/015-web-ui-overhaul/spec.md",
                snippet: "Deploy with a prepared diff and backup.",
                rank: 1,
              },
            ],
          }),
        );
      }),
      http.get("/api/knowledge/context-pack", ({ request }) => {
        const url = new URL(request.url);
        const budget = url.searchParams.get("budget") ?? "focused";
        requestedBudgets.push(budget);
        return HttpResponse.json(
          wrapEnvelope({
            available: true,
            query: url.searchParams.get("q") ?? "",
            budget,
            status: "ok",
            message: "",
            pack: {
              query: url.searchParams.get("q") ?? "",
              budget,
              matches: [
                {
                  id: "spec:config-deploy",
                  type: "spec",
                  title: "Configuration deployment",
                  resource: "specs/015-web-ui-overhaul/spec.md",
                  snippet: "Prepared diff and backup.",
                },
              ],
              expanded_concepts: [],
              evidence_edges: [],
              estimated_tokens: budget === "tiny" ? 120 : 480,
              why: ["Matches the deployment workflow."],
            },
          }),
        );
      }),
    );
    const { user } = renderModule();

    expect(await screen.findByRole("button", { name: /Graph/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(await screen.findByRole("button", { name: "React architect" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Search/ }));
    expect(screen.getByRole("button", { name: "Semantic" })).toBeDisabled();
    await user.type(
      screen.getByPlaceholderText("Describe a concept, feature, or relationship"),
      "deploy config",
    );

    expect(await screen.findByText("Configuration deployment")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Build context pack" }));

    expect(await screen.findByText("480 estimated tokens")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "focused" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "tiny" }));

    expect(await screen.findByText("120 estimated tokens")).toBeInTheDocument();
    await waitFor(() => expect(requestedBudgets).toContain("tiny"));
  });
});
