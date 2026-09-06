// Azure DevOps section content: pipeline runs and open PRs.
import { readBoolean, readString, type UnknownSection } from "@/lib/unknownFields";
import {
  type HealthFact,
  type HealthFactItem,
  pickString,
  readObjectArray,
  type SectionContent,
} from "@/modules/project-dashboard/sectionContent/types";

function buildAzureRunItem(run: Record<string, unknown>): HealthFactItem {
  const name = pickString(run, "name") ?? "Run";
  const branch = pickString(run, "sourceBranch") ?? pickString(run, "source_branch");
  const status = pickString(run, "status");
  const result = pickString(run, "result");
  const meta = [branch, result ?? status].filter((part): part is string => part !== null);
  return {
    label: name,
    meta: meta.length > 0 ? meta.join(" · ") : undefined,
    url: pickString(run, "url") ?? undefined,
  };
}

function buildAzurePullRequestItem(pr: Record<string, unknown>): HealthFactItem {
  const id = pr.id;
  const title = pickString(pr, "title") ?? "Untitled";
  const label = `#${typeof id === "number" ? id : "?"} ${title}`;
  return {
    label,
    meta: pickString(pr, "author") ?? undefined,
    url: pickString(pr, "url") ?? undefined,
  };
}

export function buildAzureDevOpsContent(section: UnknownSection): SectionContent {
  const connected = readBoolean(section, ["connected"]) ?? false;
  const org = readString(section, ["org"]);
  const devopsProject = readString(section, ["project"]);
  const runs = readObjectArray(section, "runs");
  const pullRequests = readObjectArray(section, "pull_requests");

  const facts: HealthFact[] = [];
  facts.push({
    label: "Pipeline runs",
    value: String(runs.length),
    items: runs.map(buildAzureRunItem),
  });
  facts.push({
    label: "Open PRs",
    value: String(pullRequests.length),
    items: pullRequests.map(buildAzurePullRequestItem),
  });

  const summary =
    org !== null && devopsProject !== null
      ? `${org}/${devopsProject}`
      : connected
        ? "Connected"
        : "Not connected";

  return { summary, facts, links: [] };
}
