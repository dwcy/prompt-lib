// GitHub section content: recent workflow runs, open PRs, issues, and remote branches.
import { readBoolean, readString, type UnknownSection } from "@/lib/unknownFields";
import {
  type HealthFact,
  type HealthFactItem,
  pickString,
  readObjectArray,
  type SectionContent,
} from "@/modules/project-dashboard/sectionContent/types";

function buildRunItem(run: Record<string, unknown>): HealthFactItem {
  const name = pickString(run, "name") ?? "Run";
  const branch = pickString(run, "branch");
  const status = pickString(run, "status");
  const conclusion = pickString(run, "conclusion");
  const meta = [branch, conclusion ?? status].filter((part): part is string => part !== null);
  return {
    label: name,
    meta: meta.length > 0 ? meta.join(" · ") : undefined,
    url: pickString(run, "url") ?? undefined,
  };
}

function buildPullRequestItem(pr: Record<string, unknown>): HealthFactItem {
  const number = pr.number;
  const title = pickString(pr, "title") ?? "Untitled";
  const label = `#${typeof number === "number" ? number : "?"} ${title}`;
  return {
    label,
    meta: pickString(pr, "author") ?? undefined,
    url: pickString(pr, "url") ?? undefined,
  };
}

function buildRemoteBranchItem(branch: Record<string, unknown>): HealthFactItem {
  return {
    label: pickString(branch, "name") ?? "",
    url: pickString(branch, "url") ?? undefined,
  };
}

function buildIssueItem(issue: Record<string, unknown>): HealthFactItem {
  const number = issue.number;
  const title = pickString(issue, "title") ?? "Untitled";
  const label = `#${typeof number === "number" ? number : "?"} ${title}`;
  return {
    label,
    meta: pickString(issue, "author") ?? undefined,
    url: pickString(issue, "url") ?? undefined,
  };
}

export function buildGithubContent(section: UnknownSection): SectionContent {
  const connected = readBoolean(section, ["connected"]) ?? false;
  const ownerRepo = readString(section, ["owner_repo"]);
  const remoteUsed = readString(section, ["remote_used"]);
  const runs = readObjectArray(section, "runs");
  const pullRequests = readObjectArray(section, "pull_requests");
  const remoteBranches = readObjectArray(section, "remote_branches");
  const issues = readObjectArray(section, "issues");

  const facts: HealthFact[] = [];
  if (remoteUsed !== null) facts.push({ label: "Remote", value: remoteUsed });
  facts.push({
    label: "Recent runs",
    value: String(runs.length),
    items: runs.map(buildRunItem),
  });
  facts.push({
    label: "Open PRs",
    value: String(pullRequests.length),
    items: pullRequests.map(buildPullRequestItem),
  });
  facts.push({
    label: "Issues",
    value: String(issues.length),
    items: issues.map(buildIssueItem),
  });
  facts.push({
    label: "Remote branches",
    value: String(remoteBranches.length),
    items: remoteBranches.map(buildRemoteBranchItem),
  });

  return {
    summary: ownerRepo ?? (connected ? "Connected" : "Not connected"),
    facts,
    links: [],
  };
}
