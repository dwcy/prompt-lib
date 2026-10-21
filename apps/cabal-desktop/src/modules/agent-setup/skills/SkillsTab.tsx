// Skills view of the Agent Setup module: what is installed for this machine + project, filtered
// and grouped on the left, one skill opened up on the right.
import { useMemo, useState } from "react";
import { useSkillInventory } from "@/api/agentSkills";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";
import { useModuleNavigation } from "@/hooks/useModuleNavigation";
import { SkillDetailPanel } from "./SkillDetail";
import { SkillFilterBar } from "./SkillFilterBar";
import { SkillList } from "./SkillList";
import { SkillSources } from "./SkillSources";
import { filterSkills, type SkillFilterState } from "./skillPresentation";
import "./SkillsView.css";

const INITIAL_FILTERS: SkillFilterState = { query: "", scope: "all", problemsOnly: false };

export function SkillsTab() {
  const [filters, setFilters] = useState<SkillFilterState>(INITIAL_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const inventoryQuery = useSkillInventory();
  const { navigateToModule } = useModuleNavigation();

  const skills = inventoryQuery.data?.skills ?? [];
  const visible = useMemo(() => filterSkills(skills, filters), [skills, filters]);
  const problemCount = useMemo(
    () => filterSkills(skills, { ...INITIAL_FILTERS, problemsOnly: true }).length,
    [skills],
  );

  if (inventoryQuery.isPending) {
    return <EmptyState title="Reading your installed skills" animated />;
  }
  if (inventoryQuery.isError) {
    return (
      <EmptyState title="Could not read the skill inventory" body={inventoryQuery.error.message} />
    );
  }

  const inventory = inventoryQuery.data;
  const counts = inventory.counts;
  const activeId = selectedId ?? visible[0]?.id ?? null;

  return (
    <div className="skills-tab">
      <header className="skills-tab__summary">
        <p className="skills-tab__headline">
          <strong>{counts.total ?? 0}</strong> skills reachable here — {counts.user ?? 0} personal,{" "}
          {counts.project ?? 0} from this project, {counts.plugin ?? 0} from plugins.
          {(counts.not_loaded ?? 0) > 0 ? ` ${counts.not_loaded} will not load.` : ""}
          {(counts.shadowed ?? 0) + (counts.ambiguous ?? 0) > 0
            ? ` ${(counts.shadowed ?? 0) + (counts.ambiguous ?? 0)} share a name with another definition.`
            : ""}
          {(counts.drifted ?? 0) > 0 ? ` ${counts.drifted} differ from this repo's source.` : ""}
        </p>
        <RefreshButton
          label="skill inventory"
          onRefresh={() => void inventoryQuery.refetch()}
          isFetching={inventoryQuery.isFetching}
        />
      </header>

      {inventory.project_path === null ? (
        <p className="skills-tab__notice">
          No project selected, so project skills and project-scoped plugins are not listed.{" "}
          <button
            type="button"
            className="skills-tab__link select-none"
            onClick={() => navigateToModule("project_gate")}
          >
            Choose a project
          </button>
        </p>
      ) : null}

      <SkillFilterBar
        inventory={inventory}
        filters={filters}
        problemCount={problemCount}
        onChange={setFilters}
      />

      <div className="skills-tab__body">
        <div className="skills-tab__left">
          <SkillList skills={visible} selectedId={activeId} onSelect={setSelectedId} />
          <SkillSources inventory={inventory} />
        </div>
        <SkillDetailPanel
          skillId={activeId}
          allSkills={skills}
          onSelectSkill={(skillId) => setSelectedId(skillId)}
        />
      </div>
    </div>
  );
}
