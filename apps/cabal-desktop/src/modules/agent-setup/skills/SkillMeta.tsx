// The frontmatter facts that decide how a skill behaves — the tools it may use, the model it
// pins, the argument it expects — plus the file's own size, shape and age.
import type { SkillDetail } from "@/api/agentSkills";
import { formatBytes, formatModified } from "./skillPresentation";

export interface SkillMetaProps {
  skill: SkillDetail;
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="skill-meta__fact">
      <span className="skill-meta__label select-none">{label}</span>
      <span className="skill-meta__value">{children}</span>
    </div>
  );
}

export function SkillMeta({ skill }: SkillMetaProps) {
  const modelInvocable = skill.frontmatter["disable-model-invocation"] !== true;
  return (
    <div className="skill-meta">
      <Fact label="Tools">
        {skill.allowed_tools.length === 0 ? (
          <span className="skill-meta__muted">every tool (no allowed-tools set)</span>
        ) : (
          <span className="skill-meta__tools">
            {skill.allowed_tools.map((tool) => (
              <code key={tool}>{tool}</code>
            ))}
          </span>
        )}
      </Fact>
      {skill.model !== null ? <Fact label="Model">{skill.model}</Fact> : null}
      {skill.argument_hint !== null ? (
        <Fact label="Takes">
          <code>{skill.argument_hint}</code>
        </Fact>
      ) : null}
      <Fact label="Invoked">
        {modelInvocable ? "by you or by Claude" : "only when you type it"}
      </Fact>
      <Fact label="File">
        {skill.line_count} lines · {formatBytes(skill.size_bytes)} · {skill.heading_count} headings
      </Fact>
      {skill.modified_at !== null ? (
        <Fact label="Changed">{formatModified(skill.modified_at)}</Fact>
      ) : null}
    </div>
  );
}
