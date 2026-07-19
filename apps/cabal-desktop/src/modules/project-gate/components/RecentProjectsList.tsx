// Presentational recents list: name/path/last-opened per row, click-to-select.
import type { RecentProject } from "@/api/schemas";
import { EmptyState } from "@/components/EmptyState";

export interface RecentProjectsListProps {
  recents: RecentProject[];
  onSelect: (path: string) => void;
  disabled?: boolean;
}

export function RecentProjectsList({
  recents,
  onSelect,
  disabled = false,
}: RecentProjectsListProps) {
  if (recents.length === 0) {
    return (
      <EmptyState title="No recent projects" body="This workspace has no project history yet." />
    );
  }

  const lanes = groupByRecency(recents);

  return (
    <div className="project-gate__recent-lanes">
      {lanes.map((lane) => (
        <section key={lane.label}>
          <header>
            <span>{lane.label}</span>
            <small>{lane.projects.length}</small>
          </header>
          <ul className="project-gate__recents-list">
            {lane.projects.map((recent) => (
              <li key={recent.path}>
                <button
                  type="button"
                  className="project-gate__recents-item"
                  onClick={() => onSelect(recent.path)}
                  disabled={disabled}
                >
                  <span className="project-gate__recents-mark" aria-hidden="true">
                    {projectInitial(recent.name)}
                  </span>
                  <span className="project-gate__recents-main">
                    <span className="project-gate__recents-name">{recent.name}</span>
                    <span className="project-gate__recents-path">{recent.path}</span>
                  </span>
                  <span className="project-gate__recents-meta select-none">
                    {formatLastOpened(recent.last_opened)}
                  </span>
                  <span className="project-gate__recents-enter" aria-hidden="true">
                    ›
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function groupByRecency(recents: RecentProject[]) {
  const now = Date.now();
  const day = 86_400_000;
  const lanes = [
    { label: "Today", projects: [] as RecentProject[] },
    { label: "This week", projects: [] as RecentProject[] },
    { label: "Earlier", projects: [] as RecentProject[] },
  ];
  for (const recent of recents) {
    const timestamp = new Date(recent.last_opened).getTime();
    const elapsed = Number.isNaN(timestamp)
      ? Number.POSITIVE_INFINITY
      : Math.max(0, now - timestamp);
    if (elapsed < day) lanes[0].projects.push(recent);
    else if (elapsed < day * 7) lanes[1].projects.push(recent);
    else lanes[2].projects.push(recent);
  }
  return lanes.filter((lane) => lane.projects.length > 0);
}

function formatLastOpened(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const elapsedMinutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60_000));
  if (elapsedMinutes < 1) return "just now";
  if (elapsedMinutes < 60) return `${elapsedMinutes}m ago`;
  const elapsedHours = Math.round(elapsedMinutes / 60);
  if (elapsedHours < 24) return `${elapsedHours}h ago`;
  const elapsedDays = Math.round(elapsedHours / 24);
  if (elapsedDays < 14) return `${elapsedDays}d ago`;
  return date.toLocaleDateString();
}

function projectInitial(name: string): string {
  return name.trim().charAt(0).toLocaleUpperCase() || "P";
}
