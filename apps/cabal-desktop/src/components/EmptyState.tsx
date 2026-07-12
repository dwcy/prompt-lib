// Icon-less empty/placeholder state: title, optional body copy, optional action slot.
import type { ReactNode } from "react";

export interface EmptyStateProps {
  title: string;
  body?: string;
  action?: ReactNode;
}

export function EmptyState({ title, body, action }: EmptyStateProps) {
  return (
    <div className="empty-state" role="status">
      <p className="empty-state__title select-none">{title}</p>
      {body !== undefined ? <p className="empty-state__body">{body}</p> : null}
      {action !== undefined ? <div className="empty-state__action">{action}</div> : null}
    </div>
  );
}
