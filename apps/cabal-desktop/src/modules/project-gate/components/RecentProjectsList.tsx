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
      <EmptyState
        title="No recent projects"
        body="Browse to a project folder below to get started."
      />
    );
  }

  return (
    <ul className="project-gate__recents-list">
      {recents.map((recent) => (
        <li key={recent.path}>
          <button
            type="button"
            className="project-gate__recents-item"
            onClick={() => onSelect(recent.path)}
            disabled={disabled}
          >
            <span className="project-gate__recents-name">{recent.name}</span>
            <span className="project-gate__recents-path">{recent.path}</span>
            <span className="project-gate__recents-meta select-none">
              {formatLastOpened(recent.last_opened)}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function formatLastOpened(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}
