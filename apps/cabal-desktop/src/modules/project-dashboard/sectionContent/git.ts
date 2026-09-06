// Git section content: current branch, the local-branch tree (trunk first, then namespaced
// branches grouped one level deep), worktrees, and remotes.
import { readBoolean, readString, type UnknownSection } from "@/lib/unknownFields";
import {
  type HealthFact,
  type HealthFactItem,
  NO_SUMMARY,
  pickString,
  readObjectArray,
  type SectionContent,
} from "@/modules/project-dashboard/sectionContent/types";

// Branches conventionally treated as the trunk — pinned first regardless of alphabetical order.
const TRUNK_BRANCH_NAMES = new Set(["main", "master"]);

function formatLastUsed(iso: string | null): string | undefined {
  if (iso === null) return undefined;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return undefined;
  const isoDate = date.toISOString().slice(0, 10);
  return `Last used ${isoDate}`;
}

interface BranchInfo {
  name: string;
  lastCommitAt: string | null;
  upstreamRemote: string | null;
}

function buildBranchItem(
  branch: BranchInfo,
  displayLabel: string,
  depth: number,
  currentBranch: string | null,
): HealthFactItem {
  return {
    label: displayLabel,
    meta: formatLastUsed(branch.lastCommitAt),
    origin: branch.upstreamRemote === null ? "local" : "remote",
    depth,
    current: branch.name === currentBranch,
    actionId: branch.name,
  };
}

// Trunk branch(es) first, then the rest alphabetically — grouped one level deep by their
// "namespace/leaf" prefix (e.g. all "feature/*" branches nest under a "feature" node) so the
// list reads as a shallow tree instead of a flat, unsorted dump.
function buildBranchTree(branches: BranchInfo[], currentBranch: string | null): HealthFactItem[] {
  const trunk = branches.filter((b) => TRUNK_BRANCH_NAMES.has(b.name));
  const rest = [...branches]
    .filter((b) => !TRUNK_BRANCH_NAMES.has(b.name))
    .sort((a, b) => a.name.localeCompare(b.name));

  const items: HealthFactItem[] = trunk.map((b) => buildBranchItem(b, b.name, 0, currentBranch));

  const seenGroups = new Set<string>();
  for (const branch of rest) {
    const slashIndex = branch.name.indexOf("/");
    if (slashIndex === -1) {
      items.push(buildBranchItem(branch, branch.name, 0, currentBranch));
      continue;
    }
    const group = branch.name.slice(0, slashIndex);
    const leaf = branch.name.slice(slashIndex + 1);
    if (!seenGroups.has(group)) {
      seenGroups.add(group);
      items.push({ label: group, depth: 0, group: true });
    }
    items.push(buildBranchItem(branch, leaf, 1, currentBranch));
  }

  return items;
}

function buildWorktreeItem(worktree: Record<string, unknown>): HealthFactItem {
  const path = pickString(worktree, "path") ?? "";
  const branch = pickString(worktree, "branch");
  const detached = worktree.detached === true;
  const label = branch ?? (detached ? `${path} (detached)` : path);
  const meta = [
    branch !== null ? path : undefined,
    formatLastUsed(pickString(worktree, "last_commit_at")),
  ]
    .filter((part): part is string => part !== undefined)
    .join(" · ");
  return { label, meta: meta.length > 0 ? meta : undefined, actionId: path };
}

export function buildGitContent(section: UnknownSection): SectionContent {
  const branch = readString(section, ["current_branch"]);
  const detached = readBoolean(section, ["detached"]) ?? false;
  const localBranches = readObjectArray(section, "local_branches");
  const remotes = readObjectArray(section, "remotes");
  const worktrees = readObjectArray(section, "worktrees");

  const branchInfos: BranchInfo[] = localBranches
    .map((entry): BranchInfo | null => {
      const name = pickString(entry, "name");
      return name !== null
        ? {
            name,
            lastCommitAt: pickString(entry, "last_commit_at"),
            upstreamRemote: pickString(entry, "upstream_remote"),
          }
        : null;
    })
    .filter((info): info is BranchInfo => info !== null);

  const remoteItems: HealthFactItem[] = remotes
    .map((remote): HealthFactItem | null => {
      const name = pickString(remote, "name");
      const url = pickString(remote, "url");
      return name !== null ? { label: name, url: url ?? undefined } : null;
    })
    .filter((item): item is HealthFactItem => item !== null);

  const facts: HealthFact[] = [
    {
      label: "Branch",
      value: branch !== null ? (detached ? `${branch} (detached)` : branch) : "None",
    },
    {
      label: "Local branches",
      value: String(branchInfos.length),
      items: buildBranchTree(branchInfos, branch),
      kind: "branches",
    },
    {
      label: "Worktrees",
      value: String(worktrees.length),
      items: worktrees.map(buildWorktreeItem),
      kind: "worktrees",
    },
    { label: "Remotes", value: String(remoteItems.length), items: remoteItems },
  ];

  return {
    summary: branch !== null ? (detached ? `${branch} (detached)` : `On ${branch}`) : NO_SUMMARY,
    facts,
    links: [],
  };
}
