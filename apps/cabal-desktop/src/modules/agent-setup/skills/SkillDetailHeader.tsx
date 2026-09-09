// Detail header: how you invoke the skill, what it is for, the file it lives in, and any flag
// that changes whether it runs at all. Warnings stay here rather than behind a tab.
import type { SkillDetail } from "@/api/agentSkills";
import { RefreshButton } from "@/components/RefreshButton";
import { StatePill } from "@/components/StatePill";
import { SkillPathRow } from "./SkillPathRow";
import {
  DRIFT_LABELS,
  precedenceExplanation,
  precedenceLabel,
  precedenceVariant,
  SCOPE_LABELS,
} from "./skillPresentation";

export interface SkillDetailHeaderProps {
  skill: SkillDetail;
  isFetching: boolean;
  onRefresh: () => void;
}

export function SkillDetailHeader({ skill, isFetching, onRefresh }: SkillDetailHeaderProps) {
  const precedenceNote = precedenceExplanation(skill);
  const driftsFromRepo = skill.drift === "differs";

  return (
    <header className="skill-detail__header">
      <div className="skill-detail__title-row">
        <code className="skill-detail__invocation">{skill.invocation}</code>
        <StatePill variant="unavailable" label={SCOPE_LABELS[skill.scope]} />
        {skill.kind === "command" ? <StatePill variant="unavailable" label="command" /> : null}
        <RefreshButton
          label={`${skill.invocation} detail`}
          onRefresh={onRefresh}
          isFetching={isFetching}
        />
      </div>

      {skill.description !== "" ? (
        <p className="skill-detail__description">{skill.description}</p>
      ) : (
        <p className="skill-detail__description skill-detail__description--missing">
          No description in the frontmatter — Claude has nothing to match this skill on.
        </p>
      )}

      <SkillPathRow label="File" path={skill.path} />

      {precedenceNote !== null ? (
        <div className="skill-where__flag" data-severity="warning">
          <StatePill
            variant={precedenceVariant(skill.precedence)}
            label={precedenceLabel(skill) ?? "Check"}
          />
          <span>{precedenceNote}</span>
        </div>
      ) : null}

      {driftsFromRepo ? (
        <div className="skill-where__flag" data-severity="warning">
          <StatePill variant="degraded" label={DRIFT_LABELS.differs ?? "Differs"} />
          <span>
            The applied copy no longer matches this repo's source — see the Where tab for both
            paths.
          </span>
        </div>
      ) : null}
    </header>
  );
}
