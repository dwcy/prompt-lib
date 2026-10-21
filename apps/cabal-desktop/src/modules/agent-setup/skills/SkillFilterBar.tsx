// Search box, scope switch and a "needs attention" filter for the skills list. Counts come from
// the backend inventory so the scope pills say how many are installed, not how many are shown.
import type { SkillInventory, SkillScope } from "@/api/agentSkills";
import { SCOPE_LABELS, SCOPE_ORDER, type SkillFilterState } from "./skillPresentation";

export interface SkillFilterBarProps {
  inventory: SkillInventory;
  filters: SkillFilterState;
  problemCount: number;
  onChange: (filters: SkillFilterState) => void;
}

export function SkillFilterBar({
  inventory,
  filters,
  problemCount,
  onChange,
}: SkillFilterBarProps) {
  const scopeOptions: Array<{ key: SkillScope | "all"; label: string; count: number }> = [
    { key: "all", label: "All", count: inventory.counts.total ?? 0 },
    ...SCOPE_ORDER.map((scope) => ({
      key: scope,
      label: SCOPE_LABELS[scope],
      count: inventory.counts[scope] ?? 0,
    })),
  ];

  return (
    <div className="skill-filters">
      <input
        type="search"
        className="skill-filters__search"
        placeholder="Search name or description"
        aria-label="Search skills"
        value={filters.query}
        onChange={(event) => onChange({ ...filters, query: event.target.value })}
      />
      <div className="segmented-control" role="tablist" aria-label="Skill scope">
        {scopeOptions.map((option) => (
          <button
            key={option.key}
            type="button"
            role="tab"
            aria-selected={filters.scope === option.key}
            className={`select-none${filters.scope === option.key ? " is-active" : ""}`}
            onClick={() => onChange({ ...filters, scope: option.key })}
          >
            {option.label}
            <span className="skill-filters__count">{option.count}</span>
          </button>
        ))}
      </div>
      <button
        type="button"
        className={`skill-filters__problems select-none${filters.problemsOnly ? " is-active" : ""}`}
        disabled={problemCount === 0}
        aria-pressed={filters.problemsOnly}
        onClick={() => onChange({ ...filters, problemsOnly: !filters.problemsOnly })}
      >
        Needs attention
        <span className="skill-filters__count">{problemCount}</span>
      </button>
    </div>
  );
}
