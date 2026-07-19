// Project gate & switcher: recents list + path input driving the project.select action-safety
// flow. Rendered both as the full-screen gate (App.tsx, before any project is selected) and as the
// ordinary "Project Gate & Switcher" sidebar module (switch project without restart, T036).

import { useMemo, useState } from "react";
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
  const [search, setSearch] = useState("");
  const visibleRecents = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (needle.length === 0) return projectQuery.data?.recents ?? [];
    return (projectQuery.data?.recents ?? []).filter(
      (recent) =>
        recent.name.toLowerCase().includes(needle) || recent.path.toLowerCase().includes(needle),
    );
  }, [projectQuery.data?.recents, search]);

  return (
    <div className="project-gate">
      <section className="project-gate__command-center">
        <div>
          <span className="project-gate__eyebrow select-none">Workspace launchpad</span>
          <h1>{projectQuery.data === undefined ? "Choose project context" : "Switch workspace"}</h1>
          <p>
            Project context scopes dashboards, local configuration, sessions, and repository actions
            across Cabal.
          </p>
        </div>
        {projectQuery.data !== undefined ? (
          <div className="project-gate__current select-none">
            <span>Current workspace</span>
            <strong>{projectQuery.data.name}</strong>
            <code>{projectQuery.data.path}</code>
          </div>
        ) : (
          <div className="project-gate__current project-gate__current--empty">
            <span>Current workspace</span>
            <strong>Not selected</strong>
            <small>Choose a recent project or resolve a folder path.</small>
          </div>
        )}
        <dl className="project-gate__metrics">
          <div>
            <dt>Recent</dt>
            <dd>{projectQuery.data?.recents.length ?? 0}</dd>
          </div>
          <div>
            <dt>Switch state</dt>
            <dd>{isBusy ? "review" : "ready"}</dd>
          </div>
        </dl>
      </section>

      <div className="project-gate__launchpad">
        <section className="project-gate__recents">
          <header className="project-gate__section-header">
            <div>
              <span className="module-eyebrow">History lanes</span>
              <h2 className="project-gate__section-title select-none">Recent projects</h2>
            </div>
            {projectQuery.data !== undefined ? (
              <span className="project-gate__section-count">{visibleRecents.length}</span>
            ) : null}
          </header>
          <input
            className="project-gate__search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Find a recent project"
            aria-label="Find a recent project"
          />
          {projectQuery.isPending ? (
            <EmptyState title="Loading recent projects…" />
          ) : projectQuery.isError ? (
            <EmptyState title="Could not load recent projects" body={projectQuery.error.message} />
          ) : (
            <RecentProjectsList recents={visibleRecents} onSelect={selectPath} disabled={isBusy} />
          )}
        </section>

        <aside className="project-gate__resolver">
          <header>
            <span className="module-eyebrow">Direct location</span>
            <h2>Resolve a workspace</h2>
            <p>Use a folder outside recent history without leaving the control surface.</p>
          </header>
          <PathInput onSubmit={selectPath} disabled={isBusy} />
          <ol className="project-gate__runway" aria-label="Workspace switch sequence">
            <li className="is-current">
              <span>01</span>
              <strong>Resolve folder</strong>
              <small>local path or native picker</small>
            </li>
            <li>
              <span>02</span>
              <strong>Review effects</strong>
              <small>invalidate scoped workspace data</small>
            </li>
            <li>
              <span>03</span>
              <strong>Enter workspace</strong>
              <small>refresh all project-bound modules</small>
            </li>
          </ol>
        </aside>
      </div>

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
