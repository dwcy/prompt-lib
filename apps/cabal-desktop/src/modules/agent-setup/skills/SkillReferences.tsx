// The rest of the setup a skill body points at: other skills, agents, MCP tools and real files.
// A resolved skill reference jumps straight to it; an unresolved one is left visible on purpose,
// because a skill handing off to something that is not installed is worth seeing.
import type { SkillDetail, SkillReference } from "@/api/agentSkills";
import { EmptyState } from "@/components/EmptyState";

export interface SkillReferencesProps {
  references: SkillDetail["references"];
  onSelectSkill: (skillId: string) => void;
}

const GROUP_TITLES: Array<{ key: keyof SkillDetail["references"]; title: string; hint: string }> = [
  { key: "skills", title: "Skills", hint: "Other slash commands this one names" },
  { key: "agents", title: "Agents", hint: "Subagents it hands work to" },
  { key: "tools", title: "MCP tools", hint: "Server tools it calls by name" },
  { key: "files", title: "Files", hint: "Paths it names that exist on this machine" },
];

function Chip({
  reference,
  onSelectSkill,
}: {
  reference: SkillReference;
  onSelectSkill: (skillId: string) => void;
}) {
  const targetId = reference.target_id ?? null;
  const title =
    reference.path ?? (reference.resolved ? undefined : "Not installed on this machine");
  if (targetId !== null) {
    return (
      <button
        type="button"
        className="skill-refs__chip is-linked select-none"
        title={title}
        onClick={() => onSelectSkill(targetId)}
      >
        {reference.label}
      </button>
    );
  }
  return (
    <span
      className={`skill-refs__chip select-none${reference.resolved ? "" : " is-unresolved"}`}
      title={title}
    >
      {reference.label}
      {reference.resolved ? null : <span className="skill-refs__missing">missing</span>}
    </span>
  );
}

export function SkillReferences({ references, onSelectSkill }: SkillReferencesProps) {
  const populated = GROUP_TITLES.filter((group) => references[group.key].length > 0);
  if (populated.length === 0) {
    return (
      <EmptyState
        title="No cross-references"
        body="This skill does not name another skill, agent, MCP tool or file path."
      />
    );
  }
  return (
    <div className="skill-refs">
      {populated.map((group) => (
        <section key={group.key} className="skill-refs__group">
          <h4 className="skill-refs__title select-none">
            {group.title}
            <span className="skill-refs__hint">{group.hint}</span>
          </h4>
          <div className="skill-refs__chips">
            {references[group.key].map((reference) => (
              <Chip
                key={`${group.key}-${reference.label}`}
                reference={reference}
                onSelectSkill={onSelectSkill}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
