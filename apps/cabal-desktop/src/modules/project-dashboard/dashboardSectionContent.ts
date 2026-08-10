// Builds the summary line, fact rows, and link list ProjectHealthCard renders per section — the
// dashboard payload (api/schemas.ts's dashboardSectionSchema) is a permissive record with no
// generic facts/links shape, so each section's own scalar/array fields are read and formatted here
// (git/github/supabase/vercel dataclasses per setup/src/cabal/models/dashboard.py). Never invents
// data: a fact or link only appears when the backend actually returned that field.
import type { DashboardSectionKey } from "@/api/dashboard";
import { readBoolean, readString, type UnknownSection } from "@/lib/unknownFields";

export interface HealthFact {
  label: string;
  value: string;
}

export interface HealthLink {
  label: string;
  url: string;
}

export interface SectionContent {
  summary: string;
  facts: HealthFact[];
  links: HealthLink[];
}

const NO_SUMMARY = "No summary available";

function readObjectArray(section: UnknownSection, key: string): Array<Record<string, unknown>> {
  const value = section[key];
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is Record<string, unknown> => typeof item === "object" && item !== null,
  );
}

function pickString(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function buildGitContent(section: UnknownSection): SectionContent {
  const branch = readString(section, ["current_branch"]);
  const detached = readBoolean(section, ["detached"]) ?? false;
  const localBranches = section.local_branches;
  const branchCount = Array.isArray(localBranches) ? localBranches.length : 0;
  const remotes = readObjectArray(section, "remotes");

  const facts: HealthFact[] = [
    {
      label: "Branch",
      value: branch !== null ? (detached ? `${branch} (detached)` : branch) : "None",
    },
    { label: "Local branches", value: String(branchCount) },
    { label: "Remotes", value: String(remotes.length) },
  ];
  const links: HealthLink[] = remotes
    .map((remote) => {
      const name = pickString(remote, "name");
      const url = pickString(remote, "url");
      return name !== null && url !== null ? { label: name, url } : null;
    })
    .filter((link): link is HealthLink => link !== null);

  return {
    summary: branch !== null ? (detached ? `${branch} (detached)` : `On ${branch}`) : NO_SUMMARY,
    facts,
    links,
  };
}

function buildGithubContent(section: UnknownSection): SectionContent {
  const connected = readBoolean(section, ["connected"]) ?? false;
  const ownerRepo = readString(section, ["owner_repo"]);
  const remoteUsed = readString(section, ["remote_used"]);
  const runs = readObjectArray(section, "runs");
  const pullRequests = readObjectArray(section, "pull_requests");

  const facts: HealthFact[] = [];
  if (remoteUsed !== null) facts.push({ label: "Remote", value: remoteUsed });
  facts.push({ label: "Recent runs", value: String(runs.length) });
  facts.push({ label: "Open PRs", value: String(pullRequests.length) });

  const links: HealthLink[] = [];
  const latestRun = runs[0];
  const latestRunUrl = latestRun !== undefined ? pickString(latestRun, "url") : null;
  if (latestRunUrl !== null) links.push({ label: "Latest run", url: latestRunUrl });
  for (const pr of pullRequests.slice(0, 2)) {
    const url = pickString(pr, "url");
    const number = pr.number;
    if (url !== null)
      links.push({ label: `PR #${typeof number === "number" ? number : "?"}`, url });
  }

  return {
    summary: ownerRepo ?? (connected ? "Connected" : "Not connected"),
    facts,
    links,
  };
}

function buildSupabaseContent(section: UnknownSection): SectionContent {
  const projectRef = readString(section, ["project_ref"]);
  const status = readString(section, ["status"]);
  const region = readString(section, ["region"]);
  const plan = readString(section, ["plan_name"]);
  const dbLocation = readString(section, ["db_location"]);
  const lastMigration = readString(section, ["last_migration"]);
  const lastBackup = readString(section, ["last_backup"]);
  const dashboardUrl = readString(section, ["dashboard_url"]);
  const schemaUrl = readString(section, ["schema_visualizer_url"]);

  const facts: HealthFact[] = [];
  if (status !== null) facts.push({ label: "Status", value: status });
  if (region !== null) facts.push({ label: "Region", value: region });
  if (plan !== null) facts.push({ label: "Plan", value: plan });
  if (dbLocation !== null) facts.push({ label: "DB location", value: dbLocation });
  if (lastMigration !== null) facts.push({ label: "Last migration", value: lastMigration });
  if (lastBackup !== null) facts.push({ label: "Last backup", value: lastBackup });

  const links: HealthLink[] = [];
  if (dashboardUrl !== null) links.push({ label: "Dashboard", url: dashboardUrl });
  if (schemaUrl !== null) links.push({ label: "Schema visualizer", url: schemaUrl });

  return {
    summary:
      projectRef !== null
        ? status !== null
          ? `${projectRef} · ${status}`
          : projectRef
        : NO_SUMMARY,
    facts,
    links,
  };
}

function buildVercelContent(section: UnknownSection): SectionContent {
  const projectName = readString(section, ["project_name"]);
  const plan = readString(section, ["team_plan"]);
  const region = readString(section, ["region"]);
  const deploymentStatus = readString(section, ["latest_deployment_status"]);
  const dashboardUrl = readString(section, ["dashboard_url"]);
  const deploymentUrl = readString(section, ["latest_deployment_url"]);

  const facts: HealthFact[] = [];
  if (plan !== null) facts.push({ label: "Plan", value: plan });
  if (region !== null) facts.push({ label: "Region", value: region });
  if (deploymentStatus !== null)
    facts.push({ label: "Latest deployment", value: deploymentStatus });

  const links: HealthLink[] = [];
  if (dashboardUrl !== null) links.push({ label: "Dashboard", url: dashboardUrl });
  if (deploymentUrl !== null) links.push({ label: "Latest deployment", url: deploymentUrl });

  return {
    summary:
      projectName !== null
        ? deploymentStatus !== null
          ? `${projectName} · ${deploymentStatus}`
          : projectName
        : NO_SUMMARY,
    facts,
    links,
  };
}

export function buildSectionContent(
  sectionKey: DashboardSectionKey,
  section: UnknownSection,
): SectionContent {
  switch (sectionKey) {
    case "git":
      return buildGitContent(section);
    case "github":
      return buildGithubContent(section);
    case "supabase":
      return buildSupabaseContent(section);
    case "vercel":
      return buildVercelContent(section);
  }
}
