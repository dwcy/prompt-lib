// Project gate & switcher: recents list + path input driving the project.select action-safety
// flow. Rendered both as the full-screen gate (App.tsx, before any project is selected) and as the
// ordinary "Project Gate & Switcher" sidebar module (switch project without restart, T036).
import { useProjectContext } from "@/api/project";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { PathInput } from "@/modules/project-gate/components/PathInput";
import { RecentProjectsList } from "@/modules/project-gate/components/RecentProjectsList";
import { useProjectGate } from "@/modules/project-gate/hooks/useProjectGate";

export function ProjectGateModule() {
  const projectQuery = useProjectContext();
  const { action, selectPath } = useProjectGate();
  const isBusy = action.phase === "preparing" || action.phase === "executing";

  return (
    <div className="project-gate">
      {projectQuery.data !== undefined ? (
        <p className="project-gate__current select-none">
          Current project: <strong>{projectQuery.data.name}</strong> ({projectQuery.data.path})
        </p>
      ) : null}

      <section className="project-gate__section">
        <h2 className="project-gate__section-title select-none">Recent projects</h2>
        {projectQuery.isPending ? (
          <EmptyState title="Loading recent projects…" />
        ) : projectQuery.isError ? (
          <EmptyState title="Could not load recent projects" body={projectQuery.error.message} />
        ) : (
          <RecentProjectsList
            recents={projectQuery.data.recents}
            onSelect={selectPath}
            disabled={isBusy}
          />
        )}
      </section>

      <section className="project-gate__section">
        <h2 className="project-gate__section-title select-none">Open a project</h2>
        <PathInput onSubmit={selectPath} disabled={isBusy} />
      </section>

      <ConfirmDialog
        isOpen={action.phase !== "idle"}
        actionTitle="Switch project"
        ticket={action.ticket}
        phase={action.phase}
        reviewNotice={action.reviewNotice}
        error={action.error}
        onConfirm={action.confirm}
        onCancel={action.reset}
      />
    </div>
  );
}
