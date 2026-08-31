// Dynamic tab strip for the environment browser. Tabs come only from what the backend
// reported — nothing here decides a source is worth showing, because an undetected source is
// already absent from the response (FR-005). The strip scrolls rather than truncating: every
// tab must stay reachable and every name must stay readable (FR-007).
import type { LinkConfidence, SourceState } from "@/api/envSources";

export interface EnvSourceTab {
  key: string;
  label: string;
  qualifier: string | null;
  state: SourceState | null;
  outsideRepository: boolean;
  linkConfidence: LinkConfidence | null;
  linkReason: string | null;
  count: number;
}

export interface EnvSourceTabsProps {
  tabs: EnvSourceTab[];
  activeKey: string;
  onSelect: (key: string) => void;
}

export function EnvSourceTabs({ tabs, activeKey, onSelect }: EnvSourceTabsProps) {
  return (
    <div className="env-sources__tabs" role="tablist" aria-label="Variable sources">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          role="tab"
          id={`env-tab-${tab.key}`}
          aria-selected={activeKey === tab.key}
          aria-controls={`env-panel-${tab.key}`}
          className={`env-sources__tab${activeKey === tab.key ? " is-active" : ""}`}
          data-state={tab.state ?? undefined}
          title={tabTitle(tab)}
          onClick={() => onSelect(tab.key)}
        >
          <span className="env-sources__tab-label">{tab.label}</span>
          {tab.qualifier !== null ? (
            <span className="env-sources__tab-qualifier">{tab.qualifier}</span>
          ) : null}
          {tab.outsideRepository ? (
            <span className="env-sources__badge" data-badge="outside">
              outside repo
            </span>
          ) : null}
          {tab.linkConfidence === "machine_default" ? (
            <span className="env-sources__badge" data-badge="machine-default">
              machine default
            </span>
          ) : null}
        </button>
      ))}
    </div>
  );
}

// The full name and the link reason live in the tooltip so a long vault or environment name
// stays identifiable even when the strip has scrolled it partly out of view.
function tabTitle(tab: EnvSourceTab): string {
  const parts = [tab.qualifier === null ? tab.label : `${tab.label} — ${tab.qualifier}`];
  if (tab.linkReason !== null) parts.push(tab.linkReason);
  if (tab.state !== null) parts.push(`${tab.count} ${tab.count === 1 ? "entry" : "entries"}`);
  return parts.join(" · ");
}
