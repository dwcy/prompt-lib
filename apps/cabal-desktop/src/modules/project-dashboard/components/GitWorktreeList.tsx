// Worktrees list for the Git health card: Switch selects that worktree as the active project
// (reuses project.select); Remove goes through git.remove_worktree. Both are hidden for whichever
// worktree is already the active project, mirroring the backend's own "can't remove where you are"
// guard.
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useGitWorktreeActions } from "@/modules/project-dashboard/hooks/useGitWorktreeActions";
import type { HealthFactItem } from "@/modules/project-dashboard/sectionContent";

export interface GitWorktreeListProps {
  items: HealthFactItem[];
}

function normalizePath(path: string): string {
  return path.replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
}

export function GitWorktreeList({ items }: GitWorktreeListProps) {
  const { switchAction, removeAction, activeProjectPath, switchWorktree, removeWorktree } =
    useGitWorktreeActions();
  const activeNormalized = activeProjectPath !== null ? normalizePath(activeProjectPath) : null;

  return (
    <>
      <ul className="health-card__fact-items">
        {items.map((item) => {
          const isActive =
            item.actionId !== undefined &&
            activeNormalized !== null &&
            normalizePath(item.actionId) === activeNormalized;
          return (
            <li key={item.actionId ?? item.label} className="health-card__fact-item">
              <span className="health-card__fact-item-label">{item.label}</span>
              {item.meta !== undefined ? (
                <span className="health-card__fact-item-meta">{item.meta}</span>
              ) : null}
              {item.actionId !== undefined ? (
                isActive ? (
                  <span className="health-card__fact-item-actions health-card__fact-item-actions--placeholder select-none">
                    Active
                  </span>
                ) : (
                  <span className="health-card__fact-item-actions select-none">
                    <button
                      type="button"
                      className="warning-button"
                      onClick={() => switchWorktree(item.actionId as string)}
                    >
                      Switch
                    </button>
                    <button
                      type="button"
                      className="danger-button"
                      onClick={() => removeWorktree(item.actionId as string)}
                    >
                      Remove
                    </button>
                  </span>
                )
              ) : null}
            </li>
          );
        })}
      </ul>
      <ConfirmDialog action={switchAction} actionTitle="Switch worktree" />
      <ConfirmDialog action={removeAction} actionTitle="Remove worktree" />
    </>
  );
}
