import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { EnvSourcesPayload, VariableSource } from "@/api/envSources";
import { EnvironmentModule } from "@/modules/environment/EnvironmentModule";
import { useProjectContextStore } from "@/stores/projectContext";
import {
  buildDegradedSource,
  buildEmptySource,
  buildEnvSourcesPayload,
  buildRevealResult,
  buildVariableContainer,
  buildVariableEntry,
  buildVariableSource,
  wrapEnvelope,
} from "./msw/fixtures";
import { server } from "./msw/server";

const CURATED_ENV = {
  scope: "curated" as const,
  entries: [],
  count: 0,
  editable_count: 0,
  platform: "windows",
};

function selectProject(path: string): void {
  useProjectContextStore.setState({
    selected: { path, name: path.split("/").pop() ?? path },
  } as never);
}

function mountWithSources(payload: EnvSourcesPayload) {
  server.use(
    http.get("/api/env", () => HttpResponse.json(wrapEnvelope(CURATED_ENV))),
    http.get("/api/env/sources", () => HttpResponse.json(wrapEnvelope(payload))),
  );
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <EnvironmentModule />
      </QueryClientProvider>,
    ),
  };
}

function fileSource(
  label: string,
  keys: string[],
  qualifier: string | null = null,
): VariableSource {
  const id = `repo_file:${qualifier === null ? "" : `${qualifier.replace(/\//g, "~")}~`}${label}`;
  return buildVariableSource({
    id,
    label,
    containers: [
      buildVariableContainer({
        id,
        source_id: id,
        label,
        qualifier,
        entries: keys.map((name) => buildVariableEntry({ name, source_id: id, container_id: id })),
      }),
    ],
  });
}

beforeEach(() => {
  selectProject("C:/projects/example");
});

describe("source tabs", () => {
  it("shows one tab per discovered config file alongside the built-in views", async () => {
    mountWithSources(
      buildEnvSourcesPayload([
        fileSource(".env.local", ["DATABASE_URL"]),
        fileSource("appsettings.json", ["Logging:LogLevel:Default"]),
      ]),
    );

    await screen.findByRole("tab", { name: "appsettings.json" });
    const strip = screen.getByRole("tablist", { name: "Variable sources" });

    expect(
      within(strip)
        .getAllByRole("tab")
        .map((tab) => tab.textContent),
    ).toEqual(["Curated", "System", ".env.local", "appsettings.json"]);
  });

  it("renders no value for any entry when a tab is opened", async () => {
    const user = userEvent.setup();
    mountWithSources(buildEnvSourcesPayload([fileSource(".env.local", ["DATABASE_URL"])]));

    await user.click(await screen.findByRole("tab", { name: ".env.local" }));

    expect(screen.getByText("DATABASE_URL")).toBeInTheDocument();
    expect(screen.getByLabelText("DATABASE_URL is masked")).toHaveTextContent("••••••••••••");
    expect(screen.queryByText("postgres://localhost/app")).not.toBeInTheDocument();
  });

  it("rebuilds the tabs when the selected project changes", async () => {
    const first = buildEnvSourcesPayload([fileSource(".env.local", ["A"])]);
    const second = buildEnvSourcesPayload([fileSource("appsettings.json", ["B"])]);
    let payload = first;
    server.use(
      http.get("/api/env", () => HttpResponse.json(wrapEnvelope(CURATED_ENV))),
      http.get("/api/env/sources", () => HttpResponse.json(wrapEnvelope(payload))),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <EnvironmentModule />
      </QueryClientProvider>,
    );
    await screen.findByRole("tab", { name: ".env.local" });

    payload = second;
    selectProject("C:/projects/other");
    rerender(
      <QueryClientProvider client={queryClient}>
        <EnvironmentModule />
      </QueryClientProvider>,
    );

    await screen.findByRole("tab", { name: "appsettings.json" });
    expect(screen.queryByRole("tab", { name: ".env.local" })).not.toBeInTheDocument();
  });

  it("keeps same-named files in a monorepo tellable apart", async () => {
    mountWithSources(
      buildEnvSourcesPayload([
        fileSource("appsettings.json", ["A"], "services/billing"),
        fileSource("appsettings.json", ["B"], "services/shipping"),
      ]),
    );

    await screen.findByRole("tab", { name: /services\/shipping/ });
    const strip = screen.getByRole("tablist", { name: "Variable sources" });
    const qualifiers = within(strip)
      .getAllByRole("tab")
      .map((tab) => tab.textContent);

    expect(qualifiers).toContain("appsettings.jsonservices/billing");
    expect(qualifiers).toContain("appsettings.jsonservices/shipping");
  });
});

describe("source outcomes", () => {
  it("tells an empty source apart from a degraded one in its own words", async () => {
    const user = userEvent.setup();
    mountWithSources(buildEnvSourcesPayload([buildEmptySource(), buildDegradedSource()]));

    await user.click(await screen.findByRole("tab", { name: /GitHub/ }));
    expect(screen.getByText("Nothing configured here.")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /Key Vault/ }));
    expect(screen.getByText("Key Vault is only partly readable.")).toBeInTheDocument();
    expect(screen.getByText(/az login/)).toBeInTheDocument();
  });

  it("does not render a tab for a source the backend did not report", async () => {
    mountWithSources(buildEnvSourcesPayload([fileSource(".env", ["A"])]));

    await screen.findByRole("tab", { name: ".env" });

    expect(screen.queryByRole("tab", { name: /Vercel/ })).not.toBeInTheDocument();
  });

  it("marks a machine-default Azure link as weaker than a project link", async () => {
    mountWithSources(buildEnvSourcesPayload([buildDegradedSource()]));

    const tab = await screen.findByRole("tab", { name: /Key Vault/ });

    expect(within(tab).getByText("machine default")).toBeInTheDocument();
    expect(tab).toHaveAttribute("title", expect.stringContaining("not a link to this project"));
  });

  it("refreshes one source by name rather than reloading the whole listing", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    server.use(
      http.get("/api/env", () => HttpResponse.json(wrapEnvelope(CURATED_ENV))),
      http.get("/api/env/sources", ({ request }) => {
        const only = new URL(request.url).searchParams.get("source");
        requested.push(only ?? "(all)");
        const source =
          only === null
            ? fileSource(".env", ["A"])
            : { ...fileSource(".env", ["A", "B_ADDED_ON_REFRESH"]), id: only };
        return HttpResponse.json(wrapEnvelope(buildEnvSourcesPayload([source])));
      }),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <EnvironmentModule />
      </QueryClientProvider>,
    );

    await user.click(await screen.findByRole("tab", { name: ".env" }));
    await user.click(screen.getByRole("button", { name: /Refresh \.env/ }));

    expect(await screen.findByText("B_ADDED_ON_REFRESH")).toBeInTheDocument();
    expect(requested).toEqual(["(all)", "repo_file:.env"]);
  });
});

describe("revealing one value", () => {
  async function openFileTab(entries = ["DATABASE_URL", "API_KEY"]) {
    const user = userEvent.setup();
    mountWithSources(buildEnvSourcesPayload([fileSource(".env.local", entries)]));
    await user.click(await screen.findByRole("tab", { name: ".env.local" }));
    return user;
  }

  it("reveals only the row whose eye was activated", async () => {
    server.use(
      http.post("/api/env/reveal", () => HttpResponse.json(wrapEnvelope(buildRevealResult()))),
    );
    const user = await openFileTab();

    await user.click(screen.getByRole("button", { name: "Reveal DATABASE_URL" }));

    expect(await screen.findByText("postgres://localhost/app")).toBeInTheDocument();
    expect(screen.getByLabelText("API_KEY is masked")).toHaveTextContent("••••••••••••");
  });

  it("re-masks the row when its eye is activated again", async () => {
    server.use(
      http.post("/api/env/reveal", () => HttpResponse.json(wrapEnvelope(buildRevealResult()))),
    );
    const user = await openFileTab();
    await user.click(screen.getByRole("button", { name: "Reveal DATABASE_URL" }));
    await screen.findByText("postgres://localhost/app");

    await user.click(screen.getByRole("button", { name: "Hide DATABASE_URL" }));

    expect(screen.queryByText("postgres://localhost/app")).not.toBeInTheDocument();
  });

  it("re-masks everything when the user switches tab", async () => {
    server.use(
      http.post("/api/env/reveal", () => HttpResponse.json(wrapEnvelope(buildRevealResult()))),
    );
    const user = userEvent.setup();
    mountWithSources(
      buildEnvSourcesPayload([
        fileSource(".env.local", ["DATABASE_URL"]),
        fileSource(".env.production", ["OTHER"]),
      ]),
    );
    await user.click(await screen.findByRole("tab", { name: ".env.local" }));
    await user.click(screen.getByRole("button", { name: "Reveal DATABASE_URL" }));
    await screen.findByText("postgres://localhost/app");

    await user.click(screen.getByRole("tab", { name: ".env.production" }));
    await user.click(screen.getByRole("tab", { name: ".env.local" }));

    expect(screen.queryByText("postgres://localhost/app")).not.toBeInTheDocument();
    expect(screen.getByLabelText("DATABASE_URL is masked")).toBeInTheDocument();
  });

  it("sends exactly one entry per reveal", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post("/api/env/reveal", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(wrapEnvelope(buildRevealResult()));
      }),
    );
    const user = await openFileTab();

    await user.click(screen.getByRole("button", { name: "Reveal DATABASE_URL" }));
    await screen.findByText("postgres://localhost/app");

    expect(bodies).toEqual([
      {
        source_id: "repo_file:.env.local",
        container_id: "repo_file:.env.local",
        name: "DATABASE_URL",
      },
    ]);
  });

  it("keeps the revealed value out of the query cache", async () => {
    server.use(
      http.post("/api/env/reveal", () => HttpResponse.json(wrapEnvelope(buildRevealResult()))),
    );
    const user = userEvent.setup();
    const { queryClient } = mountWithSources(
      buildEnvSourcesPayload([fileSource(".env.local", ["DATABASE_URL"])]),
    );
    await user.click(await screen.findByRole("tab", { name: ".env.local" }));

    await user.click(screen.getByRole("button", { name: "Reveal DATABASE_URL" }));
    await screen.findByText("postgres://localhost/app");

    const cached = JSON.stringify(
      queryClient
        .getQueryCache()
        .getAll()
        .map((query) => query.state.data),
    );
    expect(cached).not.toContain("postgres://localhost/app");
  });

  it("shows an empty value as an answer rather than as a failure", async () => {
    server.use(
      http.post("/api/env/reveal", () =>
        HttpResponse.json(wrapEnvelope(buildRevealResult({ value: "" }))),
      ),
    );
    const user = await openFileTab(["BLANK"]);

    await user.click(screen.getByRole("button", { name: "Reveal BLANK" }));

    expect(await screen.findByText("(empty)")).toBeInTheDocument();
  });
});

describe("retrievability", () => {
  function neverSource(): VariableSource {
    return buildVariableSource({
      id: "github",
      kind: "github",
      label: "GitHub",
      outside_repository: true,
      containers: [
        buildVariableContainer({
          id: "github:repository",
          source_id: "github",
          label: "Repository",
          qualifier: "GitHub",
          entries: [
            buildVariableEntry({
              name: "REGION",
              source_id: "github",
              container_id: "github:repository",
            }),
          ],
        }),
        buildVariableContainer({
          id: "github:repository:secrets",
          source_id: "github",
          label: "Repository secrets",
          qualifier: "GitHub",
          entries: [
            buildVariableEntry({
              name: "DEPLOY_KEY",
              source_id: "github",
              container_id: "github:repository:secrets",
              entry_type: "secret",
              retrievability: "never",
              retrievability_reason: "GitHub never returns secret values",
            }),
          ],
        }),
      ],
    });
  }

  it("offers no working eye on an entry that can never be retrieved", async () => {
    const user = userEvent.setup();
    mountWithSources(buildEnvSourcesPayload([neverSource()]));

    await user.click(await screen.findByRole("tab", { name: /GitHub/ }));

    expect(
      screen.getByRole("button", { name: "Value cannot be retrieved for DEPLOY_KEY" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reveal REGION" })).toBeEnabled();
  });

  it("states the reason a value can never be retrieved without calling it an error", async () => {
    const user = userEvent.setup();
    mountWithSources(buildEnvSourcesPayload([neverSource()]));

    await user.click(await screen.findByRole("tab", { name: /GitHub/ }));

    expect(screen.getByText("GitHub never returns secret values")).toBeInTheDocument();
    expect(screen.queryByText(/error|failed/i)).not.toBeInTheDocument();
  });

  it("reports a permission denial on the row and leaves the rest of the list usable", async () => {
    server.use(
      http.post("/api/env/reveal", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildRevealResult({
              status: "denied",
              value: null,
              reason: "requires the Key Vault Secrets User role",
            }),
          ),
        ),
      ),
    );
    const user = userEvent.setup();
    mountWithSources(buildEnvSourcesPayload([fileSource(".env", ["A", "B"])]));
    await user.click(await screen.findByRole("tab", { name: ".env" }));

    await user.click(screen.getByRole("button", { name: "Reveal A" }));

    expect(await screen.findByText(/Permission denied/)).toBeInTheDocument();
    expect(screen.getByText(/Key Vault Secrets User role/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reveal B" })).toBeEnabled();
  });

  it("marks a key vault reference as a reference rather than a resolved secret", async () => {
    server.use(
      http.post("/api/env/reveal", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildRevealResult({
              value: "@Microsoft.KeyVault(SecretUri=https://kv/x)",
              is_reference: true,
            }),
          ),
        ),
      ),
    );
    const user = userEvent.setup();
    mountWithSources(buildEnvSourcesPayload([fileSource(".env", ["REF"])]));
    await user.click(await screen.findByRole("tab", { name: ".env" }));

    await user.click(screen.getByRole("button", { name: "Reveal REF" }));

    expect(await screen.findByText("reference")).toBeInTheDocument();
    expect(screen.getByText("@Microsoft.KeyVault(SecretUri=https://kv/x)")).toBeInTheDocument();
  });
});

describe(".NET layers and the developer secret store", () => {
  it("lists hierarchical keys as fully-qualified paths and names the winning layer", async () => {
    const user = userEvent.setup();
    const id = "repo_file:appsettings.Development.json";
    mountWithSources(
      buildEnvSourcesPayload([
        buildVariableSource({
          id,
          label: "appsettings.Development.json",
          containers: [
            buildVariableContainer({
              id,
              source_id: id,
              label: "appsettings.Development.json",
              layer: {
                stack: "dotnet",
                name: "appsettings.Development.json",
                rank: 4,
                wins: true,
              },
              entries: [
                buildVariableEntry({
                  name: "Logging:LogLevel:Default",
                  source_id: id,
                  container_id: id,
                }),
              ],
            }),
          ],
        }),
      ]),
    );

    await user.click(await screen.findByRole("tab", { name: "appsettings.Development.json" }));

    expect(screen.getByText("Logging:LogLevel:Default")).toBeInTheDocument();
    expect(screen.getByText("wins")).toBeInTheDocument();
  });

  it("badges the developer secret store as living outside the repository", async () => {
    mountWithSources(
      buildEnvSourcesPayload([
        buildVariableSource({
          id: "dotnet_secrets:abc-123",
          kind: "dotnet_secrets",
          label: "User secrets",
          outside_repository: true,
          containers: [
            buildVariableContainer({
              id: "dotnet_secrets:abc-123",
              source_id: "dotnet_secrets:abc-123",
              label: "User secrets (abc-123)",
              qualifier: "Api/Api.csproj",
              entries: [
                buildVariableEntry({
                  name: "ConnectionStrings:Db",
                  source_id: "dotnet_secrets:abc-123",
                  container_id: "dotnet_secrets:abc-123",
                }),
              ],
            }),
          ],
        }),
      ]),
    );

    const tab = await screen.findByRole("tab", { name: /User secrets/ });

    expect(within(tab).getByText("outside repo")).toBeInTheDocument();
  });
});

describe("Vercel grouping", () => {
  it("groups entries by deployment target", async () => {
    const user = userEvent.setup();
    mountWithSources(
      buildEnvSourcesPayload([
        buildVariableSource({
          id: "vercel",
          kind: "vercel",
          label: "Vercel",
          outside_repository: true,
          containers: ["preview", "production"].map((target) =>
            buildVariableContainer({
              id: `vercel:${target}`,
              source_id: "vercel",
              label: target,
              qualifier: "Vercel",
              entries: [
                buildVariableEntry({
                  name: "API_BASE",
                  source_id: "vercel",
                  container_id: `vercel:${target}`,
                  target,
                  entry_type: "encrypted",
                  retrievability: "permission_gated",
                  retrievability_reason: "reading this value requires a token",
                }),
              ],
            }),
          ),
        }),
      ]),
    );

    await user.click(await screen.findByRole("tab", { name: /Vercel/ }));

    expect(screen.getByRole("heading", { name: /preview/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /production/ })).toBeInTheDocument();
  });
});

describe("the explicit Azure link", () => {
  it("states which signal established the link and offers to record a scope", async () => {
    const user = userEvent.setup();
    mountWithSources(buildEnvSourcesPayload([buildDegradedSource()]));

    await user.click(await screen.findByRole("tab", { name: /Key Vault/ }));

    expect(screen.getByText(/this machine's default Azure sign-in/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record scope" })).toBeDisabled();
  });

  it("enables clearing only when the link is one the user recorded", async () => {
    const user = userEvent.setup();
    mountWithSources(
      buildEnvSourcesPayload([
        buildDegradedSource({
          link_confidence: "explicit",
          link_reason: "an Azure scope you recorded for this project",
        }),
      ]),
    );

    await user.click(await screen.findByRole("tab", { name: /Key Vault/ }));

    expect(screen.getByRole("button", { name: "Clear" })).toBeEnabled();
  });
});

describe("one slow source never blocks the module", () => {
  it("renders every other source while one is reported degraded", async () => {
    const user = userEvent.setup();
    mountWithSources(
      buildEnvSourcesPayload([
        fileSource(".env.local", ["DATABASE_URL"]),
        buildDegradedSource({
          hint: "Key Vault did not respond within 2.5s — refresh this tab to wait longer",
        }),
      ]),
    );

    await user.click(await screen.findByRole("tab", { name: ".env.local" }));

    expect(screen.getByText("DATABASE_URL")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Key Vault/ })).toBeEnabled();
  });

  it("keeps the four source outcomes visually distinct from one another", async () => {
    mountWithSources(
      buildEnvSourcesPayload([
        fileSource(".env", ["A"]),
        buildEmptySource(),
        buildDegradedSource(),
      ]),
    );

    await screen.findByRole("tab", { name: ".env" });
    const strip = screen.getByRole("tablist", { name: "Variable sources" });
    const states = within(strip)
      .getAllByRole("tab")
      .map((tab) => tab.getAttribute("data-state"));

    // Curated and System carry no source state; the three real sources each carry their own,
    // and `not_linked` is absent by construction — an undetected source has no tab at all.
    expect(states).toEqual([null, null, "ok", "empty", "degraded"]);
  });
});
