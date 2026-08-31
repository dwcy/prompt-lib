// One fact row in a Project Health card — plain label/value, or a self-toggling expandable row
// that reveals its item list and any nested sub-facts. Branch/worktree facts (fact.kind) delegate
// their item list entirely to a specialized, action-aware renderer instead of the generic one.
import { useState } from "react";
import { GitBranchTree } from "@/modules/project-dashboard/components/GitBranchTree";
import { GitWorktreeList } from "@/modules/project-dashboard/components/GitWorktreeList";
import type { HealthFact } from "@/modules/project-dashboard/sectionContent";

export interface HealthFactRowProps {
  fact: HealthFact;
}

export function HealthFactRow({ fact }: HealthFactRowProps) {
  const [expanded, setExpanded] = useState(false);
  const expandable = (fact.items?.length ?? 0) > 0 || (fact.nested?.length ?? 0) > 0;

  if (!expandable) {
    return (
      <div className="health-card__fact-group">
        <div className="health-card__fact">
          <span className="health-card__fact-label">{fact.label}</span>
          <span className="health-card__fact-value">{fact.value}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="health-card__fact-group">
      <button
        type="button"
        className="health-card__fact health-card__fact--expandable"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
      >
        <span className="health-card__fact-label">{fact.label}</span>
        <span className="health-card__fact-value">
          {fact.value}
          <span className="health-card__fact-chevron" aria-hidden="true">
            ▸
          </span>
        </span>
      </button>
      <div className="health-card__fact-panel" data-expanded={expanded}>
        <div className="health-card__fact-panel-inner">
          {fact.items !== undefined && fact.items.length > 0 ? (
            fact.kind === "branches" ? (
              <GitBranchTree items={fact.items} />
            ) : fact.kind === "worktrees" ? (
              <GitWorktreeList items={fact.items} />
            ) : (
              <ul className="health-card__fact-items">
                {fact.items.map((item) => (
                  <li
                    key={item.url ?? item.label}
                    className="health-card__fact-item"
                    data-group={item.group ? "true" : undefined}
                    data-current={item.current ? "true" : undefined}
                    style={item.depth ? { paddingLeft: `${item.depth * 1}rem` } : undefined}
                  >
                    {item.current ? (
                      <span className="health-card__fact-item-dot" aria-hidden="true" />
                    ) : null}
                    {item.url !== undefined ? (
                      <a
                        className="health-card__fact-item-label"
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {item.label}
                      </a>
                    ) : (
                      <span className="health-card__fact-item-label">{item.label}</span>
                    )}
                    {item.meta !== undefined ? (
                      <span className="health-card__fact-item-meta">{item.meta}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )
          ) : null}
          {fact.nested?.map((sub) => (
            <HealthFactRow key={sub.label} fact={sub} />
          ))}
        </div>
      </div>
    </div>
  );
}
