// Icon-less empty/placeholder state: title, optional body copy, optional action slot.
// `animated` appends a CSS-only cycling ellipsis (".", "..", "...") for in-flight loading titles.
import type { ReactNode } from "react";

export interface EmptyStateProps {
  title: string;
  body?: string;
  action?: ReactNode;
  animated?: boolean;
}

export function EmptyState({ title, body, action, animated = false }: EmptyStateProps) {
  return (
    <div className="empty-state" role="status">
      <p className="empty-state__title select-none">
        {title}
        {animated ? <span className="empty-state__dots" aria-hidden="true" /> : null}
      </p>
      {body !== undefined ? <p className="empty-state__body">{body}</p> : null}
      {action !== undefined ? <div className="empty-state__action">{action}</div> : null}
    </div>
  );
}
