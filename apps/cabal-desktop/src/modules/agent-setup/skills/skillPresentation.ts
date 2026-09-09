// Labels, badge variants, search and grouping for the Skills view. Keeps the wording of "where
// this came from" and "does it actually load" in one place so list and detail never disagree.
import type { SkillDrift, SkillPrecedence, SkillScope, SkillSummary } from "@/api/agentSkills";
import type { StatePillVariant } from "@/components/StatePill";

export { formatBytes, formatModified } from "../agentSetupFormat";

export const SCOPE_LABELS: Record<SkillScope, string> = {
  user: "Personal",
  project: "Project",
  plugin: "Plugin",
};

export const SCOPE_ORDER: SkillScope[] = ["user", "project", "plugin"];

export const SCOPE_HINTS: Record<SkillScope, string> = {
  user: "From your home config — available in every project on this machine.",
  project: "From this project's .claude folder — only available while you work here.",
  plugin: "Installed from a marketplace plugin — namespaced as /plugin:skill.",
};

export function precedenceLabel(skill: SkillSummary): string | null {
  switch (skill.precedence) {
    case "shadowed":
      return "Overridden";
    case "ambiguous":
      return "Defined twice";
    case "not_loaded":
      return "Not loaded";
    default:
      return null;
  }
}

export function precedenceVariant(precedence: SkillPrecedence): StatePillVariant {
  return precedence === "not_loaded" ? "failed" : "degraded";
}

/** The plain-language consequence of a duplicate name, or null when there is nothing to warn about. */
export function precedenceExplanation(skill: SkillSummary): string | null {
  const count = skill.duplicates.length;
  if (skill.precedence === "not_loaded") {
    return skill.not_loaded_reason;
  }
  if (skill.precedence === "shadowed") {
    return `Another copy of ${skill.invocation} in a narrower scope wins — this file is not the one that runs.`;
  }
  if (skill.precedence === "ambiguous") {
    return `${count + 1} definitions of ${skill.invocation} sit in the same scope, so scope alone does not decide which one loads.`;
  }
  return null;
}

export const DRIFT_LABELS: Record<SkillDrift, string | null> = {
  in_sync: "Matches repo",
  differs: "Differs from repo",
  not_in_repo: "Not from this repo",
  not_applicable: null,
};

export function driftVariant(drift: SkillDrift): StatePillVariant {
  if (drift === "differs") return "degraded";
  if (drift === "in_sync") return "ok";
  return "unavailable";
}

export function driftExplanation(
  skill: SkillSummary,
  repoSourcePath: string | null,
): string | null {
  switch (skill.drift) {
    case "in_sync":
      return `The applied copy is identical to this repo's source at ${repoSourcePath ?? "global/skills"}.`;
    case "differs":
      return `The applied copy no longer matches this repo's source at ${repoSourcePath ?? "global/skills"} — one of the two was edited without a deploy.`;
    case "not_in_repo":
      return "No matching source in this repo's global/skills — it was added straight to your home config.";
    default:
      return null;
  }
}

export interface SkillFilterState {
  query: string;
  scope: SkillScope | "all";
  problemsOnly: boolean;
}

function hasProblem(skill: SkillSummary): boolean {
  return !skill.loaded || skill.precedence !== "effective" || skill.drift === "differs";
}

export function filterSkills(skills: SkillSummary[], filters: SkillFilterState): SkillSummary[] {
  const needle = filters.query.trim().toLowerCase();
  return skills.filter((skill) => {
    if (filters.scope !== "all" && skill.scope !== filters.scope) return false;
    if (filters.problemsOnly && !hasProblem(skill)) return false;
    if (needle === "") return true;
    const haystack = `${skill.invocation} ${skill.name} ${skill.description} ${skill.plugin ?? ""}`;
    return haystack.toLowerCase().includes(needle);
  });
}

export interface SkillGroup {
  key: string;
  label: string;
  hint: string;
  skills: SkillSummary[];
}

/** Personal, then project, then one group per plugin — the order they take precedence in. */
export function groupSkills(skills: SkillSummary[]): SkillGroup[] {
  const groups = new Map<string, SkillGroup>();
  for (const scope of SCOPE_ORDER) {
    for (const skill of skills.filter((item) => item.scope === scope)) {
      const key = skill.plugin !== null ? `plugin:${skill.plugin}` : scope;
      const label = skill.plugin !== null ? `${skill.plugin} plugin` : SCOPE_LABELS[scope];
      const existing = groups.get(key);
      if (existing === undefined) {
        groups.set(key, { key, label, hint: SCOPE_HINTS[scope], skills: [skill] });
      } else {
        existing.skills.push(skill);
      }
    }
  }
  return [...groups.values()];
}
