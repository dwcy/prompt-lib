// Skills view of the Agent Setup module: the inventory list, the flags that say a skill will not
// load or is overridden, and the detail pane's outline / where-it-lives / bundled-file reads.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { SkillDetail, SkillInventory, SkillSummary } from "@/api/agentSkills";
import { AgentSetupModule } from "@/modules/agent-setup/AgentSetupModule";
import { renderInline } from "@/modules/agent-setup/skills/skillInline";
import { filterSkills, groupSkills } from "@/modules/agent-setup/skills/skillPresentation";
import { wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

function skill(overrides: Partial<SkillSummary> = {}): SkillSummary {
  return {
    id: "user:skill:tui",
    name: "tui",
    invocation: "/tui",
    scope: "user",
    kind: "skill",
    plugin: null,
    marketplace: null,
    plugin_enabled: null,
    description: "Textual TUI conventions",
    allowed_tools: ["Read", "Bash"],
    model: null,
    argument_hint: null,
    path: "C:/Users/me/.claude/skills/tui/SKILL.md",
    dir_path: "C:/Users/me/.claude/skills/tui",
    size_bytes: 12288,
    line_count: 240,
    heading_count: 9,
    modified_at: "2026-01-01T00:00:00Z",
    bundled_count: 0,
    loaded: true,
    not_loaded_reason: null,
    precedence: "effective",
    duplicates: [],
    drift: "in_sync",
    ...overrides,
  };
}

function inventory(skills: SkillSummary[]): SkillInventory {
  const counts: Record<string, number> = {
    total: skills.length,
    loaded: skills.filter((item) => item.loaded).length,
    not_loaded: skills.filter((item) => !item.loaded).length,
    shadowed: skills.filter((item) => item.precedence === "shadowed").length,
    ambiguous: 0,
    drifted: skills.filter((item) => item.drift === "differs").length,
    user: skills.filter((item) => item.scope === "user").length,
    project: skills.filter((item) => item.scope === "project").length,
    plugin: skills.filter((item) => item.scope === "plugin").length,
  };
  return {
    project_path: "C:/projects/demo",
    claude_home: "C:/Users/me/.claude",
    repo_skills_path: "C:/projects/demo/global/skills",
    counts,
    sources: [
      {
        key: "user-skills",
        label: "Personal skills",
        scope: "user",
        path: "C:/Users/me/.claude/skills",
        exists: true,
        count: counts.user,
        plugin_version: null,
        plugin_enabled: null,
      },
      {
        key: "user-commands",
        label: "Personal commands",
        scope: "user",
        path: "C:/Users/me/.claude/commands",
        exists: false,
        count: 0,
        plugin_version: null,
        plugin_enabled: null,
      },
    ],
    skills,
    unapplied_repo_skills: [],
  };
}

function detail(summary: SkillSummary, overrides: Partial<SkillDetail> = {}): SkillDetail {
  return {
    ...summary,
    frontmatter_raw: "name: tui\ndescription: Textual TUI conventions",
    frontmatter: { name: "tui" },
    preamble: [],
    sections: [
      {
        level: 2,
        title: "Rule 1 - Ctrl+C is copy",
        anchor: "rule-1",
        blocks: [
          { type: "paragraph", text: "Never bind ctrl+c to quit." },
          { type: "code", language: "python", text: "BINDINGS = []" },
        ],
      },
      {
        level: 2,
        title: "Rule 2 - Clipboard",
        anchor: "rule-2",
        blocks: [{ type: "paragraph", text: "Read the OS clipboard." }],
      },
    ],
    raw: "---\nname: tui\n---\n\n## Rule 1",
    truncated: false,
    bundled_files: [],
    references: { skills: [], agents: [], tools: [], files: [] },
    repo_source_path: "C:/projects/demo/global/skills/tui/SKILL.md",
    ...overrides,
  };
}

function mount(payload: SkillInventory, detailPayload: SkillDetail) {
  server.use(
    http.get("/api/agent-config/skills", () => HttpResponse.json(wrapEnvelope(payload))),
    http.get("/api/agent-config/skills/detail", () =>
      HttpResponse.json(wrapEnvelope(detailPayload)),
    ),
    http.get("/api/agent-config/skills/asset", () =>
      HttpResponse.json(
        wrapEnvelope({
          skill_id: detailPayload.id,
          rel_path: "references/notes.md",
          path: `${detailPayload.dir_path}/references/notes.md`,
          content: "bundled notes body",
          binary: false,
          truncated: false,
          size_bytes: 18,
        }),
      ),
    ),
  );
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AgentSetupModule />
    </QueryClientProvider>,
  );
}

describe("Skills inventory", () => {
  it("opens on the skills view and counts what is reachable by scope", async () => {
    const project = skill({
      id: "project:skill:readme",
      name: "readme",
      invocation: "/readme",
      scope: "project",
    });
    mount(inventory([skill(), project]), detail(skill()));

    const headline = await screen.findByText(/skills reachable here/);

    expect(headline.textContent).toContain("1 personal, 1 from this project, 0 from plugins");
  });

  it("groups skills by where they come from", () => {
    const grouped = groupSkills([
      skill(),
      skill({ id: "project:skill:readme", scope: "project" }),
      skill({ id: "plugin:skill:azure/azure-cost", scope: "plugin", plugin: "azure" }),
    ]);

    expect(grouped.map((group) => group.label)).toEqual(["Personal", "Project", "azure plugin"]);
  });

  it("flags a loose markdown file as one that will not load", async () => {
    const loose = skill({
      id: "project:skill:standup",
      name: "standup",
      invocation: "/standup",
      scope: "project",
      loaded: false,
      not_loaded_reason: "A skill has to be a folder with a SKILL.md inside it.",
      precedence: "not_loaded",
      dir_path: null,
      drift: "not_applicable",
    });
    mount(inventory([loose]), detail(loose));

    expect(await screen.findByText("Not loaded")).toBeInTheDocument();
    expect(
      await screen.findByText(/A skill has to be a folder with a SKILL.md inside it/),
    ).toBeInTheDocument();
  });

  it("keeps only the skills that need attention when that filter is on", () => {
    const healthy = skill();
    const overridden = skill({ id: "user:skill:readme", precedence: "shadowed" });

    const filtered = filterSkills([healthy, overridden], {
      query: "",
      scope: "all",
      problemsOnly: true,
    });

    expect(filtered.map((item) => item.id)).toEqual(["user:skill:readme"]);
  });

  it("narrows the list by a search term", () => {
    const filtered = filterSkills(
      [skill(), skill({ id: "b", name: "git", invocation: "/git", description: "" })],
      {
        query: "textual",
        scope: "all",
        problemsOnly: false,
      },
    );

    expect(filtered.map((item) => item.invocation)).toEqual(["/tui"]);
  });
});

describe("Skill detail", () => {
  it("shows the file it lives in without leaving the header", async () => {
    mount(inventory([skill()]), detail(skill()));

    const header = await screen.findByText("C:/Users/me/.claude/skills/tui/SKILL.md");

    expect(header).toBeInTheDocument();
  });

  it("puts the repo source and drift verdict behind the Where tab", async () => {
    mount(inventory([skill()]), detail(skill()));

    await userEvent.click(await screen.findByRole("tab", { name: "Where" }));
    const where = screen.getByLabelText("Where this skill lives");

    expect(within(where).getByText("Matches repo")).toBeInTheDocument();
  });

  it("renders the body as collapsed headings that expand on click", async () => {
    mount(inventory([skill()]), detail(skill()));

    const secondHeading = await screen.findByRole("button", { name: /Rule 2 - Clipboard/ });
    expect(secondHeading).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Read the OS clipboard.")).not.toBeInTheDocument();

    await userEvent.click(secondHeading);

    expect(secondHeading).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Read the OS clipboard.")).toBeInTheDocument();
  });

  it("reads a bundled reference file only when it is picked", async () => {
    mount(
      inventory([skill({ bundled_count: 1 })]),
      detail(skill({ bundled_count: 1 }), {
        bundled_files: [
          {
            name: "notes.md",
            rel_path: "references/notes.md",
            group: "references",
            size_bytes: 18,
            previewable: true,
          },
        ],
      }),
    );

    await userEvent.click(await screen.findByRole("tab", { name: /Bundled \(1\)/ }));
    expect(screen.queryByText("bundled notes body")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /notes.md/ }));

    expect(await screen.findByText("bundled notes body")).toBeInTheDocument();
  });

  it("links a cross-referenced skill to the skill it resolves to", async () => {
    const target = skill({ id: "user:skill:git", name: "git", invocation: "/git" });
    mount(
      inventory([skill(), target]),
      detail(skill(), {
        references: {
          skills: [{ label: "/git", target_id: "user:skill:git", resolved: true }],
          agents: [{ label: "@nowhere-agent", target_id: null, resolved: false }],
          tools: [],
          files: [],
        },
      }),
    );

    await userEvent.click(await screen.findByRole("tab", { name: "References" }));

    expect(screen.getByRole("button", { name: "/git" })).toBeInTheDocument();
    expect(screen.getByText("missing")).toBeInTheDocument();
  });
});

describe("Inline markdown", () => {
  it("renders backticked text as code and leaves the surrounding words alone", () => {
    const nodes = renderInline("Use `Ctrl+C` to copy");

    expect(nodes).toHaveLength(3);
    expect(nodes[0]).toBe("Use ");
    expect(nodes[2]).toBe(" to copy");
  });
});

describe("Config files tab", () => {
  it("still reaches the folder browser", async () => {
    mount(inventory([skill()]), detail(skill()));
    server.use(
      http.get("/api/agent-config/tree", () =>
        HttpResponse.json(
          wrapEnvelope({
            agent: "claude",
            scope: "global",
            base_path: "C:/Users/me/.claude",
            exists: true,
            roots: [],
            truncated: false,
          }),
        ),
      ),
    );

    await userEvent.click(await screen.findByRole("tab", { name: "Config files" }));

    expect(await screen.findByRole("tab", { name: "Antigravity" })).toBeInTheDocument();
  });
});
