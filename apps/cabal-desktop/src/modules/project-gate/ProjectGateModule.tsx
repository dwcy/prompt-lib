// Project gate & switcher: recents list + path input driving the project.select action-safety
// flow. Rendered both as the full-screen gate (App.tsx, before any project is selected) and as the
// ordinary "Project Gate & Switcher" sidebar module (switch project without restart, T036).

import { useMemo, useState } from "react";
import { useProjectContext } from "@/api/project";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";
import { PathInput } from "@/modules/project-gate/components/PathInput";
import { RecentProjectsList } from "@/modules/project-gate/components/RecentProjectsList";
import { useProjectGate } from "@/modules/project-gate/hooks/useProjectGate";
import "./ProjectGateModule.css";

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
    <div className="gate">
      <section className="gate-header">
        <div className="gate-header__intro">
          <span className="gate-eyebrow select-none">Workspace launchpad</span>
          <h1>{projectQuery.data === undefined ? "Choose project context" : "Switch workspace"}</h1>
          <p>
            Project context scopes dashboards, local configuration, sessions, and repository actions
            across Cabal.
          </p>
        </div>
        {projectQuery.data !== undefined ? (
          <div className="gate-current select-none">
            <span>Current workspace</span>
            <strong>{projectQuery.data.name}</strong>
            <code>{projectQuery.data.path}</code>
          </div>
        ) : (
          <div className="gate-current gate-current--empty">
            <span>Current workspace</span>
            <strong>Not selected</strong>
            <small>Choose a recent project or resolve a folder path.</small>
          </div>
        )}
        <dl className="gate-metrics">
          <div>
            <dt>Recent</dt>
            <dd>{projectQuery.data?.recents.length ?? 0}</dd>
          </div>
          <div>
            <dt>Switch state</dt>
            <dd>{isBusy ? "review" : "ready"}</dd>
          </div>
        </dl>
        <CardRefreshFooter>
          <RefreshButton
            label="project context"
            onRefresh={() => void projectQuery.refetch()}
            isFetching={projectQuery.isFetching}
          />
        </CardRefreshFooter>
      </section>

      <div className="gate-layout">
        <section className="gate-recents">
          <header className="gate-panel__header">
            <div>
              <span className="gate-eyebrow">History lanes</span>
              <h2 className="gate-panel__title select-none">Recent projects</h2>
            </div>
            {projectQuery.data !== undefined ? (
              <span className="gate-panel__count">{visibleRecents.length}</span>
            ) : null}
          </header>
          <input
            className="gate-search"
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

        <aside className="gate-resolver">
          <header className="gate-resolver__header">
            <span className="gate-eyebrow">Direct location</span>
            <h2>Resolve a workspace</h2>
            <p>Use a folder outside recent history without leaving the control surface.</p>
          </header>
          <PathInput onSubmit={selectPath} disabled={isBusy} />
          <ol className="gate-runway" aria-label="Workspace switch sequence">
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

      <ConfirmDialog action={action} actionTitle="Switch project" />
    </div>
  );
}
