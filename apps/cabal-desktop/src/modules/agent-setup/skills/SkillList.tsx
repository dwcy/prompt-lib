// The installed skills as a browsable list, grouped by where they come from. Each row carries
// only what you scan by: how you invoke it, what it is for, and a flag when it will not load.
import type { SkillSummary } from "@/api/agentSkills";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";
import { DRIFT_LABELS, groupSkills, precedenceLabel, precedenceVariant } from "./skillPresentation";

export interface SkillListProps {
  skills: SkillSummary[];
  selectedId: string | null;
  onSelect: (skillId: string) => void;
}

function SkillRow({
  skill,
  selected,
  onSelect,
}: {
  skill: SkillSummary;
  selected: boolean;
  onSelect: (skillId: string) => void;
}) {
  const flag = precedenceLabel(skill);
  return (
    <li>
      <button
        type="button"
        className={`skill-list__row${selected ? " is-selected" : ""}`}
        aria-current={selected}
        onClick={() => onSelect(skill.id)}
      >
        <span className="skill-list__row-top">
          <code className="skill-list__invocation">{skill.invocation}</code>
          {flag !== null ? (
            <StatePill variant={precedenceVariant(skill.precedence)} label={flag} />
          ) : null}
          {skill.drift === "differs" ? (
            <StatePill variant="degraded" label={DRIFT_LABELS.differs ?? "Differs"} />
          ) : null}
        </span>
        <span className="skill-list__description">
          {skill.description === "" ? "No description" : skill.description}
        </span>
        <span className="skill-list__meta">
          {skill.heading_count} headings
          {skill.bundled_count > 0 ? ` · ${skill.bundled_count} bundled files` : ""}
        </span>
      </button>
    </li>
  );
}

export function SkillList({ skills, selectedId, onSelect }: SkillListProps) {
  if (skills.length === 0) {
    return (
      <EmptyState
        title="Nothing matches"
        body="No installed skill matches the current search and filters."
      />
    );
  }
  return (
    <div className="skill-list">
      {groupSkills(skills).map((group) => (
        <section key={group.key} className="skill-list__group">
          <h3 className="skill-list__group-title select-none" title={group.hint}>
            {group.label}
            <span className="skill-list__group-count">{group.skills.length}</span>
          </h3>
          <ul>
            {group.skills.map((skill) => (
              <SkillRow
                key={skill.id}
                skill={skill}
                selected={skill.id === selectedId}
                onSelect={onSelect}
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
