// One skill opened up: its heading outline, the folder it lives in, the files it bundles, what it
// cross-references, and the raw file underneath — with the frontmatter facts always in view.
import { useState } from "react";
import { type SkillSummary, useSkillDetail } from "@/api/agentSkills";
import { EmptyState } from "@/components/EmptyState";
import { SkillBundles } from "./SkillBundles";
import { SkillDetailHeader } from "./SkillDetailHeader";
import { SkillMeta } from "./SkillMeta";
import { SkillOutline } from "./SkillOutline";
import { SkillReferences } from "./SkillReferences";
import { SkillWhere } from "./SkillWhere";

type DetailTab = "structure" | "where" | "bundled" | "references" | "raw";

export interface SkillDetailPanelProps {
  skillId: string | null;
  allSkills: SkillSummary[];
  onSelectSkill: (skillId: string) => void;
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <section className="skill-detail" aria-label="Skill detail">
      {children}
    </section>
  );
}

export function SkillDetailPanel({ skillId, allSkills, onSelectSkill }: SkillDetailPanelProps) {
  const [tab, setTab] = useState<DetailTab>("structure");
  const detailQuery = useSkillDetail(skillId);

  if (skillId === null) {
    return (
      <Shell>
        <EmptyState
          title="Pick a skill to open it"
          body="You get its instructions as a collapsible outline, the exact file it lives in, and everything it pulls in."
        />
      </Shell>
    );
  }
  if (detailQuery.isPending) {
    return (
      <Shell>
        <EmptyState title="Reading the skill" animated />
      </Shell>
    );
  }
  if (detailQuery.isError) {
    return (
      <Shell>
        <EmptyState title="Could not read that skill" body={detailQuery.error.message} />
      </Shell>
    );
  }

  const skill = detailQuery.data;
  const duplicates = allSkills.filter((item) => skill.duplicates.includes(item.id));
  const bundledLabel =
    skill.bundled_files.length > 0 ? `Bundled (${skill.bundled_files.length})` : "Bundled";
  const tabs: Array<{ key: DetailTab; label: string }> = [
    { key: "structure", label: "Structure" },
    { key: "where", label: "Where" },
    { key: "bundled", label: bundledLabel },
    { key: "references", label: "References" },
    { key: "raw", label: "Raw file" },
  ];

  return (
    <Shell>
      <SkillDetailHeader
        skill={skill}
        isFetching={detailQuery.isFetching}
        onRefresh={() => void detailQuery.refetch()}
      />
      <SkillMeta skill={skill} />

      <div className="segmented-control skill-detail__tabs" role="tablist" aria-label="Skill view">
        {tabs.map((entry) => (
          <button
            key={entry.key}
            type="button"
            role="tab"
            aria-selected={tab === entry.key}
            className={`select-none${tab === entry.key ? " is-active" : ""}`}
            onClick={() => setTab(entry.key)}
          >
            {entry.label}
          </button>
        ))}
      </div>

      <div className="skill-detail__body">
        {tab === "structure" ? (
          <SkillOutline key={skill.id} preamble={skill.preamble} sections={skill.sections} />
        ) : null}
        {tab === "where" ? (
          <SkillWhere skill={skill} duplicates={duplicates} onSelectSkill={onSelectSkill} />
        ) : null}
        {tab === "bundled" ? (
          <SkillBundles key={skill.id} skillId={skill.id} files={skill.bundled_files} />
        ) : null}
        {tab === "references" ? (
          <SkillReferences references={skill.references} onSelectSkill={onSelectSkill} />
        ) : null}
        {tab === "raw" ? (
          <>
            <pre className="skill-detail__raw">{skill.raw}</pre>
            {skill.truncated ? (
              <p className="skill-detail__truncated">
                Shown up to the preview limit — the file on disk is longer.
              </p>
            ) : null}
          </>
        ) : null}
      </div>
    </Shell>
  );
}
