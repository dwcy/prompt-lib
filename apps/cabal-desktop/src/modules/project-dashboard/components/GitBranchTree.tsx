// Local-branches tree for the Git health card: main/master first, then namespaced branches
// grouped one level deep, each leaf with Switch/Delete buttons through the action-safety protocol.
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useGitBranchActions } from "@/modules/project-dashboard/hooks/useGitBranchActions";
import type { HealthFactItem } from "@/modules/project-dashboard/sectionContent";

export interface GitBranchTreeProps {
  items: HealthFactItem[];
}

export function GitBranchTree({ items }: GitBranchTreeProps) {
  const { switchAction, deleteAction, switchBranch, deleteBranch } = useGitBranchActions();

  return (
    <>
      <ul className="health-card__fact-items">
        {items.map((item) => (
          <li
            key={item.actionId ?? item.label}
            className="health-card__fact-item"
            data-group={item.group ? "true" : undefined}
            data-current={item.current ? "true" : undefined}
            style={item.depth ? { paddingLeft: `${item.depth * 1}rem` } : undefined}
          >
            {item.current ? (
              <span className="health-card__fact-item-dot" aria-hidden="true" />
            ) : null}
            <span className="health-card__fact-item-label">{item.label}</span>
            {item.origin !== undefined ? (
              <span className="health-card__fact-item-origin" data-origin={item.origin}>
                {item.origin === "local" ? "Local" : "Remote"}
              </span>
            ) : null}
            {item.meta !== undefined ? (
              <span className="health-card__fact-item-meta">{item.meta}</span>
            ) : null}
            {!item.group && item.actionId !== undefined ? (
              item.current ? (
                <span className="health-card__fact-item-actions health-card__fact-item-actions--placeholder select-none">
                  Current
                </span>
              ) : (
                <span className="health-card__fact-item-actions select-none">
                  <button
                    type="button"
                    className="warning-button"
                    onClick={() => switchBranch(item.actionId as string)}
                  >
                    Switch
                  </button>
                  <button
                    type="button"
                    className="danger-button"
                    onClick={() => deleteBranch(item.actionId as string)}
                  >
                    Delete
                  </button>
                </span>
              )
            ) : null}
          </li>
        ))}
      </ul>
      <ConfirmDialog action={switchAction} actionTitle="Switch branch" />
      <ConfirmDialog action={deleteAction} actionTitle="Delete branch" />
    </>
  );
}
