// "Where this skill lives" tab: the folder and repo source behind the file, what its scope means,
// which copy wins when a name is defined twice, and how the applied copy compares to repo source.
import type { SkillDetail, SkillSummary } from "@/api/agentSkills";
import { StatePill } from "@/components/StatePill";
import { SkillPathRow } from "./SkillPathRow";
import {
  DRIFT_LABELS,
  driftExplanation,
  driftVariant,
  SCOPE_HINTS,
  SCOPE_LABELS,
} from "./skillPresentation";

export interface SkillWhereProps {
  skill: SkillDetail;
  duplicates: SkillSummary[];
  onSelectSkill: (skillId: string) => void;
}

export function SkillWhere({ skill, duplicates, onSelectSkill }: SkillWhereProps) {
  const driftNote = driftExplanation(skill, skill.repo_source_path);
  const driftLabel = DRIFT_LABELS[skill.drift];

  return (
    <section className="skill-where" aria-label="Where this skill lives">
      <SkillPathRow label="File" path={skill.path} />
      {skill.dir_path !== null && skill.dir_path !== skill.path ? (
        <SkillPathRow label="Folder" path={skill.dir_path} />
      ) : null}
      {skill.repo_source_path !== null ? (
        <SkillPathRow label="Repo source" path={skill.repo_source_path} />
      ) : null}

      <p className="skill-where__hint">
        <strong>{SCOPE_LABELS[skill.scope]}.</strong> {SCOPE_HINTS[skill.scope]}
      </p>

      {skill.plugin !== null ? (
        <p className="skill-where__hint">
          Shipped by the <strong>{skill.plugin}</strong> plugin
          {skill.marketplace !== null ? ` from the ${skill.marketplace} marketplace` : ""}
          {skill.plugin_enabled === false ? " — currently switched off." : "."}
        </p>
      ) : null}

      {driftLabel !== null ? (
        <div className="skill-where__flag">
          <StatePill variant={driftVariant(skill.drift)} label={driftLabel} />
          <span>{driftNote}</span>
        </div>
      ) : null}

      {duplicates.length > 0 ? (
        <div className="skill-where__duplicates">
          <span className="skill-where__label select-none">Also defined in</span>
          <ul>
            {duplicates.map((duplicate) => (
              <li key={duplicate.id}>
                <button
                  type="button"
                  className="skill-where__duplicate select-none"
                  onClick={() => onSelectSkill(duplicate.id)}
                >
                  {SCOPE_LABELS[duplicate.scope]} · {duplicate.kind} · {duplicate.path}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
