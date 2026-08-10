// Segmented-pill tab switcher for the Graph / Search / Context pack / Reports workbenches.
export type KnowledgeTab = "graph" | "search" | "packs" | "reports";

const TABS: Array<{ key: KnowledgeTab; label: string }> = [
  { key: "graph", label: "Graph" },
  { key: "search", label: "Search" },
  { key: "packs", label: "Context pack" },
  { key: "reports", label: "Reports" },
];

export interface KnowledgeTabsBarProps {
  tab: KnowledgeTab;
  onTabChange: (tab: KnowledgeTab) => void;
}

export function KnowledgeTabsBar({ tab, onTabChange }: KnowledgeTabsBarProps) {
  return (
    <fieldset className="km-tabs">
      <legend className="km-vh">Knowledge view</legend>
      {TABS.map((item) => (
        <button
          key={item.key}
          type="button"
          className={tab === item.key ? "is-active" : undefined}
          aria-pressed={tab === item.key}
          onClick={() => onTabChange(item.key)}
        >
          {item.label}
        </button>
      ))}
    </fieldset>
  );
}
