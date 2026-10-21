// Narrows the deploy tree to one kind of config — agents, skills, hooks, rules — because the
// full tree is well over a hundred files. Counts are per group so a chip says how much is behind
// it, and how much of that has drifted.
import type { ConfigComponent } from "@/api/config";

export const ALL_GROUPS = "all";

export interface DeployGroupFilterProps {
  components: ConfigComponent[];
  active: string;
  onChange: (group: string) => void;
}

interface GroupTally {
  key: string;
  label: string;
  files: number;
  drifted: number;
}

/** One tally per group in tree order, plus an "All" tally covering every component. */
export function tallyGroups(components: ConfigComponent[]): GroupTally[] {
  const byGroup = new Map<string, GroupTally>();
  let allFiles = 0;
  let allDrifted = 0;

  for (const component of components) {
    const drifted = component.files.filter((file) => file.state !== "unchanged").length;
    allFiles += component.files.length;
    allDrifted += drifted;
    const existing = byGroup.get(component.group);
    if (existing === undefined) {
      byGroup.set(component.group, {
        key: component.group,
        label: component.group,
        files: component.files.length,
        drifted,
      });
    } else {
      existing.files += component.files.length;
      existing.drifted += drifted;
    }
  }

  return [
    { key: ALL_GROUPS, label: "All", files: allFiles, drifted: allDrifted },
    ...byGroup.values(),
  ];
}

export function DeployGroupFilter({ components, active, onChange }: DeployGroupFilterProps) {
  const tallies = tallyGroups(components);

  return (
    <div className="cfg-deploy__group-filter" role="tablist" aria-label="Config group">
      {tallies.map((tally) => (
        <button
          key={tally.key}
          type="button"
          role="tab"
          aria-selected={active === tally.key}
          className={`cfg-deploy__group-chip select-none${active === tally.key ? " is-active" : ""}`}
          onClick={() => onChange(tally.key)}
        >
          {tally.label}
          <span className="cfg-deploy__group-chip-count">{tally.files}</span>
          {tally.drifted > 0 ? (
            <span className="cfg-deploy__group-chip-drift">{tally.drifted} drifted</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}
